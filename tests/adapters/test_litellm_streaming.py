"""Streaming send for the LiteLLM adapter (docs/TODO/06)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.contracts import ProviderRequest
from packages.contracts.streaming_models import StreamCompleted, StreamError, StreamStarted, StreamTextDelta
from packages.core.orchestration.streaming import run_streaming_turn
from packages.adapters.providers.litellm import litellm_provider
from packages.adapters.providers.litellm import LiteLLMProvider


def _request() -> ProviderRequest:
    return ProviderRequest(
        schema_version="1",
        trace_id="trace-stream",
        turn_id="turn-stream",
        model="local-model",
        input_text="hello",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )


def _chunk(text: str | None, *, chunk_id: str = "resp-1", event_type: str = "response.output_text.delta") -> object:
    return SimpleNamespace(id=chunk_id, delta=text, type=event_type)


def _text_done(text: str) -> object:
    return SimpleNamespace(
        id="resp-1",
        type="response.output_text.done",
        item_id="msg-1",
        output_index=0,
        content_index=0,
        text=text,
    )


def _reasoning_done(text: str) -> object:
    return SimpleNamespace(
        id="resp-1",
        type="response.reasoning_text.done",
        item_id="rs-1",
        output_index=0,
        content_index=0,
        text=text,
    )


def _completed_with_sdk_sequences(response_id: str, text: str) -> object:
    return SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(
            id=response_id,
            output=(
                SimpleNamespace(
                    type="message",
                    content=(SimpleNamespace(type="output_text", text=text),),
                ),
            ),
        ),
    )


def test_stream_send_yields_deltas_then_completed_and_sets_stream_flag(monkeypatch):
    captured: dict[str, object] = {}

    def fake_responses(**kwargs):
        captured.update(kwargs)
        return iter([_chunk("Hel"), _chunk("lo"), _chunk(None, event_type="response.completed")])

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    events = list(LiteLLMProvider().stream_send(_request()))
    assert captured["stream"] is True
    assert isinstance(events[0], StreamStarted) and events[0].response_id == "resp-1"
    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["Hel", "lo"]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].response_id == "resp-1"
    assert events[-1].output_text == "Hello"
    assert events[-1].finish_reason == "stop"


def test_stream_send_uses_output_text_done_when_delta_was_absent(monkeypatch):
    def fake_responses(**_kwargs):
        return iter([_text_done("Done text"), _chunk(None, event_type="response.completed")])

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    events = list(LiteLLMProvider().stream_send(_request()))
    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["Done text"]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].output_text == "Done text"


def test_stream_send_reads_completed_text_from_sdk_sequence_collections(monkeypatch):
    def fake_responses(**_kwargs):
        return iter([_completed_with_sdk_sequences("resp-sequence", "Sequence reply")])

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    events = list(LiteLLMProvider().stream_send(_request()))

    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].response_id == "resp-sequence"
    assert events[-1].output_text == "Sequence reply"


def test_stream_send_uses_reasoning_done_when_delta_was_absent(monkeypatch):
    def fake_responses(**_kwargs):
        return iter([
            _reasoning_done("Finished reasoning."),
            _chunk("Final."),
            _chunk(None, event_type="response.completed"),
        ])

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    events = list(LiteLLMProvider().stream_send(_request()))
    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["<think>", "Finished reasoning.", "</think>", "Final."]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].output_text == "<think>Finished reasoning.</think>Final."


def test_stream_send_drives_through_run_streaming_turn(monkeypatch):
    def fake_responses(**_kwargs):
        return iter([_chunk("Mar"), _chunk("vex"), _chunk(None, event_type="response.completed")])

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    sink: list[str] = []
    result = run_streaming_turn(LiteLLMProvider().stream_send(_request()), on_delta=sink.append)
    assert result.status == "completed"
    assert result.text == "Marvex"
    assert result.response_id == "resp-1"
    assert sink == ["Mar", "vex"]


def test_stream_send_maps_failure_to_stream_error(monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(litellm_provider.litellm, "responses", boom)

    events = list(LiteLLMProvider().stream_send(_request()))
    assert len(events) == 1
    assert isinstance(events[0], StreamError)


def test_stream_error_redacts_api_key(monkeypatch):
    from packages.adapters.providers.litellm.litellm_provider import LiteLLMProviderConfig

    def boom(**_kwargs):
        raise RuntimeError("bad key sk-secret-123")

    monkeypatch.setattr(litellm_provider.litellm, "responses", boom)

    provider = LiteLLMProvider(LiteLLMProviderConfig(api_key="sk-secret-123"))
    events = list(provider.stream_send(_request()))
    assert isinstance(events[0], StreamError)
    assert "sk-secret-123" not in events[0].message
    assert "[REDACTED]" in events[0].message
