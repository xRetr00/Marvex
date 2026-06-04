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


def _text_done(text: str) -> object:
    return SimpleNamespace(
        type="response.output_text.done",
        item_id="msg-1",
        output_index=0,
        content_index=0,
        text=text,
    )


def _completed(response_id: str, text: str) -> object:
    return SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(id=response_id, output_text=text),
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


def test_stream_send_yields_deltas_then_completed_and_sets_stream_flag():
    provider, client = _provider([_delta("Hel"), _delta("lo"), _completed("resp-9", "Hello")])
    events = list(provider.stream_send(_request()))
    assert client.responses.captured["stream"] is True
    assert isinstance(events[0], StreamTextDelta) and events[0].text == "Hel"
    assert isinstance(events[1], StreamTextDelta) and events[1].text == "lo"
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].response_id == "resp-9"
    assert events[-1].output_text == "Hello"


def test_stream_send_reads_completed_text_from_sdk_sequence_collections():
    provider, _ = _provider([_completed_with_sdk_sequences("resp-sequence", "Sequence reply")])

    events = list(provider.stream_send(_request()))

    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].response_id == "resp-sequence"
    assert events[-1].output_text == "Sequence reply"


def test_stream_send_drives_through_run_streaming_turn():
    provider, _ = _provider([_delta("Mar"), _delta("vex"), _completed("r1", "Marvex")])
    sink: list[str] = []
    result = run_streaming_turn(provider.stream_send(_request()), on_delta=sink.append)
    assert result.status == "completed"
    assert result.text == "Marvex"
    assert result.response_id == "r1"
    assert sink == ["Mar", "vex"]


def test_stream_send_uses_output_text_done_when_delta_was_absent():
    provider, _ = _provider([_text_done("Done text"), _completed("r-done", "Done text")])

    events = list(provider.stream_send(_request()))

    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["Done text"]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].output_text == "Done text"


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


def _completed_with_tool_call(response_id: str, call_id: str, name: str, args: str) -> object:
    return SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(
            id=response_id,
            output_text="",
            output=[
                SimpleNamespace(
                    type="function_call",
                    name=name,
                    arguments=args,
                    call_id=call_id,
                )
            ],
        ),
    )


def test_stream_send_captures_tool_calls_on_completed():
    provider, _ = _provider(
        [
            _delta("<think>navigate</think>"),
            _completed_with_tool_call("resp-tool", "call-1", "builtin.playwright_browser", '{"url":"https://x"}'),
        ]
    )
    events = list(provider.stream_send(_request()))
    completed = events[-1]
    assert isinstance(completed, StreamCompleted)
    assert completed.tool_calls is not None
    assert completed.tool_calls[0]["function"]["name"] == "builtin.playwright_browser"
    assert completed.tool_calls[0]["function"]["arguments"] == '{"url":"https://x"}'
    assert completed.tool_calls[0]["id"] == "call-1"


def _reasoning_delta(text: str) -> object:
    return SimpleNamespace(type="response.reasoning_text.delta", delta=text)


def _reasoning_summary_delta(text: str) -> object:
    return SimpleNamespace(type="response.reasoning_summary_text.delta", delta=text)


def _reasoning_done(text: str) -> object:
    return SimpleNamespace(
        type="response.reasoning_text.done",
        item_id="rs-1",
        output_index=0,
        content_index=0,
        text=text,
    )


def test_stream_send_surfaces_reasoning_text_inside_think_block():
    provider, _ = _provider(
        [
            _reasoning_delta("Plan"),
            _reasoning_delta(" it"),
            _delta("Answer"),
            _completed("r-think", "Answer"),
        ]
    )
    events = list(provider.stream_send(_request()))
    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["<think>", "Plan", " it", "</think>", "Answer"]
    completed = events[-1]
    assert isinstance(completed, StreamCompleted)
    assert completed.output_text == "<think>Plan it</think>Answer"


def test_stream_send_uses_reasoning_done_when_delta_was_absent():
    provider, _ = _provider(
        [
            _reasoning_done("Finished reasoning."),
            _delta("Final."),
            _completed("r-reasoning-done", "Final."),
        ]
    )

    events = list(provider.stream_send(_request()))

    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["<think>", "Finished reasoning.", "</think>", "Final."]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].output_text == "<think>Finished reasoning.</think>Final."


def test_stream_send_closes_reasoning_when_summary_channel_used():
    provider, _ = _provider(
        [
            _reasoning_summary_delta("thinking"),
            _completed("r-sum", ""),
        ]
    )
    events = list(provider.stream_send(_request()))
    deltas = [event.text for event in events if isinstance(event, StreamTextDelta)]
    assert deltas == ["<think>", "thinking", "</think>"]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].output_text == "<think>thinking</think>"


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
