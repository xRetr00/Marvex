"""Tests for the streaming provider turn driver (docs/TODO/06 foundation)."""

from packages.core.orchestration.streaming import (
    StreamCompleted,
    StreamError,
    StreamTextDelta,
    run_streaming_turn,
)


def test_deltas_are_forwarded_in_order_and_accumulated():
    sink: list[str] = []
    events = [
        StreamTextDelta("Hel"),
        StreamTextDelta("lo "),
        StreamTextDelta("world"),
        StreamCompleted(response_id="resp-1", finish_reason="stop", output_text="Hello world"),
    ]
    result = run_streaming_turn(events, on_delta=sink.append)
    assert result.status == "completed"
    assert result.text == "Hello world"
    assert result.response_id == "resp-1"
    assert result.delta_count == 3
    assert sink == ["Hel", "lo ", "world"]


def test_final_output_text_reconciles_when_more_complete():
    # Provider sends a corrected/fuller final text than the concatenated deltas.
    events = [
        StreamTextDelta("Hello"),
        StreamCompleted(response_id="r", finish_reason="stop", output_text="Hello, world!"),
    ]
    result = run_streaming_turn(events)
    assert result.text == "Hello, world!"


def test_deltas_kept_when_final_output_text_is_shorter():
    events = [
        StreamTextDelta("Hello world"),
        StreamCompleted(response_id="r", finish_reason="stop", output_text=""),
    ]
    result = run_streaming_turn(events)
    assert result.text == "Hello world"


def test_error_event_returns_error_with_partial_text():
    events = [StreamTextDelta("Partial"), StreamError("provider blew up")]
    result = run_streaming_turn(events)
    assert result.status == "error"
    assert result.text == "Partial"
    assert result.error_message == "provider blew up"


def test_stream_without_terminal_event_is_graceful():
    result = run_streaming_turn([StreamTextDelta("a"), StreamTextDelta("b")])
    assert result.status == "completed"
    assert result.text == "ab"


def test_empty_deltas_are_skipped():
    sink: list[str] = []
    events = [StreamTextDelta(""), StreamTextDelta("x"), StreamCompleted(None, "stop", "x")]
    result = run_streaming_turn(events, on_delta=sink.append)
    assert sink == ["x"]
    assert result.text == "x"


def test_failing_sink_does_not_abort_generation():
    def boom(_chunk: str) -> None:
        raise RuntimeError("UI detached")

    events = [StreamTextDelta("a"), StreamTextDelta("b"), StreamCompleted(None, "stop", "ab")]
    result = run_streaming_turn(events, on_delta=boom)
    assert result.status == "completed"
    assert result.text == "ab"
