"""Streaming send for the LMStudio Responses adapter (docs/TODO/06)."""

from __future__ import annotations

from types import SimpleNamespace

from packages.contracts import ProviderRequest
from packages.contracts.streaming_models import StreamCompleted, StreamError, StreamTextDelta
from packages.core.orchestration.streaming import run_streaming_turn
from packages.adapters.providers.lmstudio_responses.lmstudio_responses_provider import (
    LMStudioResponsesProvider,
    LMStudioResponsesProviderConfig,
)


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


class _FakeResponses:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self.captured: dict[str, object] = {}

    def create(self, **kwargs: object) -> list[object]:
        self.captured = kwargs
        return self._events


class _FakeClient:
    def __init__(self, events: list[object]) -> None:
        self.responses = _FakeResponses(events)


def _provider(events: list[object]) -> tuple[LMStudioResponsesProvider, _FakeClient]:
    client = _FakeClient(events)
    provider = LMStudioResponsesProvider(
        config=LMStudioResponsesProviderConfig(),
        client_factory=lambda **_kwargs: client,
    )
    return provider, client


def _delta(text: str) -> object:
    return SimpleNamespace(type="response.output_text.delta", delta=text)


def _completed(response_id: str, text: str) -> object:
    return SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(id=response_id, output_text=text),
    )


def test_stream_send_yields_deltas_then_completed_and_sets_stream_flag():
    provider, client = _provider([_delta("Hel"), _delta("lo"), _completed("resp-9", "Hello")])
    events = list(provider.stream_send(_request()))
    assert client.responses.captured["stream"] is True
    assert isinstance(events[0], StreamTextDelta) and events[0].text == "Hel"
    assert isinstance(events[1], StreamTextDelta) and events[1].text == "lo"
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].response_id == "resp-9"
    assert events[-1].output_text == "Hello"


def test_stream_send_drives_through_run_streaming_turn():
    provider, _ = _provider([_delta("Mar"), _delta("vex"), _completed("r1", "Marvex")])
    sink: list[str] = []
    result = run_streaming_turn(provider.stream_send(_request()), on_delta=sink.append)
    assert result.status == "completed"
    assert result.text == "Marvex"
    assert result.response_id == "r1"
    assert sink == ["Mar", "vex"]


def test_stream_send_maps_client_failure_to_stream_error():
    class _BoomClient:
        @property
        def responses(self):
            raise RuntimeError("connection refused")

    provider = LMStudioResponsesProvider(
        config=LMStudioResponsesProviderConfig(),
        client_factory=lambda **_kwargs: _BoomClient(),
    )
    events = list(provider.stream_send(_request()))
    assert len(events) == 1
    assert isinstance(events[0], StreamError)


def test_send_remains_non_streaming_and_unchanged():
    # The non-streaming path must not set stream=True.
    captured: dict[str, object] = {}

    class _Resp:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(id="r", output_text="ok", usage=None, output=[])

    class _Client:
        responses = _Resp()

    provider = LMStudioResponsesProvider(
        config=LMStudioResponsesProviderConfig(),
        client_factory=lambda **_kwargs: _Client(),
    )
    result = provider.send(_request())
    assert "stream" not in captured
    assert result.error is None
