"""Streaming send for the LiteLLM adapter (docs/TODO/06)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.contracts import ProviderRequest
from packages.contracts.streaming_models import StreamCompleted, StreamError, StreamTextDelta
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


def _chunk(text: str | None, *, chunk_id: str = "chat-1", finish: str | None = None) -> object:
    delta = SimpleNamespace(content=text)
    choice = SimpleNamespace(delta=delta, finish_reason=finish)
    return SimpleNamespace(id=chunk_id, choices=[choice])


def test_stream_send_yields_deltas_then_completed_and_sets_stream_flag(monkeypatch):
    captured: dict[str, object] = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return iter([_chunk("Hel"), _chunk("lo"), _chunk(None, finish="stop")])

    monkeypatch.setattr(litellm_provider.litellm, "completion", fake_completion)

    events = list(LiteLLMProvider().stream_send(_request()))
    assert captured["stream"] is True
    assert isinstance(events[0], StreamTextDelta) and events[0].text == "Hel"
    assert isinstance(events[1], StreamTextDelta) and events[1].text == "lo"
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].response_id == "chat-1"
    assert events[-1].output_text == "Hello"
    assert events[-1].finish_reason == "stop"


def test_stream_send_drives_through_run_streaming_turn(monkeypatch):
    def fake_completion(**_kwargs):
        return iter([_chunk("Mar"), _chunk("vex"), _chunk(None, finish="stop")])

    monkeypatch.setattr(litellm_provider.litellm, "completion", fake_completion)

    sink: list[str] = []
    result = run_streaming_turn(LiteLLMProvider().stream_send(_request()), on_delta=sink.append)
    assert result.status == "completed"
    assert result.text == "Marvex"
    assert result.response_id == "chat-1"
    assert sink == ["Mar", "vex"]


def test_stream_send_maps_failure_to_stream_error(monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(litellm_provider.litellm, "completion", boom)

    events = list(LiteLLMProvider().stream_send(_request()))
    assert len(events) == 1
    assert isinstance(events[0], StreamError)


def test_stream_error_redacts_api_key(monkeypatch):
    from packages.adapters.providers.litellm.litellm_provider import LiteLLMProviderConfig

    def boom(**_kwargs):
        raise RuntimeError("bad key sk-secret-123")

    monkeypatch.setattr(litellm_provider.litellm, "completion", boom)

    provider = LiteLLMProvider(LiteLLMProviderConfig(api_key="sk-secret-123"))
    events = list(provider.stream_send(_request()))
    assert isinstance(events[0], StreamError)
    assert "sk-secret-123" not in events[0].message
    assert "[REDACTED]" in events[0].message
