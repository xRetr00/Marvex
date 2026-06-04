from __future__ import annotations

from types import SimpleNamespace

from packages.assistant_runtime.result_assembly import build_text_final_response
from packages.contracts import AssistantTurnResult


def _result(text: str) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version="1",
        trace_id="trace-stream-turn",
        turn_id="turn-stream-turn",
        assistant_final_response=build_text_final_response(schema_version="1", text=text),
        output_events=[],
        stage_summaries=[],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )


def _request() -> object:
    return SimpleNamespace(
        assistant_turn_input=SimpleNamespace(),
        previous_response_id=None,
        resume_approval_id=None,
        approval_decision=None,
    )


def test_stream_turn_events_emits_live_deltas_and_tool_then_final():
    from services.core.main import (
        _active_live_event_sink,
        _active_live_token_sink,
        _stream_turn_events,
    )

    class _Service:
        def submit_turn(self, turn_input, **kwargs):
            # Simulate the provider streaming tokens and a tool step live, using
            # the per-thread sinks the handler installs on this worker thread.
            token = _active_live_token_sink()
            event = _active_live_event_sink()
            token("<think>look</think>")
            event({"type": "tool", "phase": "start", "id": "c1", "name": "file.search", "arguments": '{"query":"x"}'})
            token("Done")
            return _result("<think>look</think>Done")

    events = list(_stream_turn_events(_Service(), _request()))
    types = [e["type"] for e in events]

    assert types == ["delta", "tool", "delta", "final"]
    assert events[0]["text"] == "<think>look</think>"
    assert events[1]["name"] == "file.search"
    assert events[2]["text"] == "Done"
    assert events[-1]["result"]["assistant_final_response"]["text"] == "<think>look</think>Done"


def test_stream_turn_events_preserves_model_authored_commentary_frame():
    from services.core.main import (
        _active_live_event_sink,
        _active_live_token_sink,
        _stream_turn_events,
    )

    class _Service:
        def submit_turn(self, turn_input, **kwargs):
            token = _active_live_token_sink()
            event = _active_live_event_sink()
            token("I'm locating MAR.txt.")
            event({"type": "commentary", "text": "I'm locating MAR.txt."})
            event({"type": "tool", "phase": "start", "id": "c1", "name": "file.read"})
            token("The file contains test data.")
            return _result("The file contains test data.")

    events = list(_stream_turn_events(_Service(), _request()))
    assert [event["type"] for event in events] == ["delta", "commentary", "tool", "delta", "final"]
    assert events[1]["text"] == "I'm locating MAR.txt."


def test_stream_turn_events_falls_back_to_chunking_when_no_live_deltas():
    from services.core.main import _stream_turn_events

    class _NonStreamingService:
        def submit_turn(self, turn_input, **kwargs):
            return _result("Plain answer here")

    events = list(_stream_turn_events(_NonStreamingService(), _request()))
    assert events[-1]["type"] == "final"
    # No live deltas -> the final text is chunk-streamed as a fallback.
    deltas = [e["text"] for e in events if e["type"] == "delta"]
    assert "".join(deltas) == "Plain answer here"


def test_stream_turn_events_maps_timeout_to_error_event():
    from services.core.main import _stream_turn_events

    class _BoomService:
        def submit_turn(self, turn_input, **kwargs):
            raise TimeoutError("slow")

    events = list(_stream_turn_events(_BoomService(), _request()))
    assert events[-1]["type"] == "error"
    assert events[-1]["reason"] == "provider_timeout"
