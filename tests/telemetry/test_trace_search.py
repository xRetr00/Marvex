from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts import TraceEvent, TraceLevel, TraceStage
from packages.telemetry.search import TraceSearchQuery, search_traces
from packages.telemetry.trace_reader import InMemoryTraceReader


def _emit(reader: InMemoryTraceReader, trace_id: str, *, session_id: str, conversation_id: str, status: str) -> None:
    reader.emit(
        TraceEvent(
            schema_version="1",
            trace_id=trace_id,
            event_id=f"turn-{trace_id}:complete",
            timestamp=datetime(2026, 5, 18, tzinfo=UTC),
            stage=TraceStage.TURN_COMPLETED,
            level=TraceLevel.INFO,
            message="completed without raw payload",
            data={
                "status": status,
                "session_ref": {"ref_type": "session", "ref_id": session_id},
                "conversation_ref": {"ref_type": "conversation", "ref_id": conversation_id},
                "tool_status": "approved",
                "raw_provider_payload": "secret-token-123",
            },
        )
    )


def test_trace_search_filters_by_safe_session_conversation_and_status() -> None:
    reader = InMemoryTraceReader()
    _emit(reader, "trace-1", session_id="session-1", conversation_id="conversation-1", status="completed")
    _emit(reader, "trace-2", session_id="session-2", conversation_id="conversation-2", status="failed")

    result = search_traces(
        reader,
        TraceSearchQuery(
            schema_version="1",
            session_ref_id="session-1",
            conversation_ref_id="conversation-1",
            status="completed",
            tool_status="approved",
            max_results=10,
        ),
        trace_ids=("trace-1", "trace-2"),
    )

    assert result.match_count == 1
    assert result.traces[0].trace_id == "trace-1"
    assert result.traces[0].raw_payload_persisted is False
    assert "secret-token" not in str(result.safe_projection()).lower()


def test_trace_search_result_is_bounded() -> None:
    reader = InMemoryTraceReader()
    _emit(reader, "trace-1", session_id="session-1", conversation_id="conversation-1", status="completed")
    _emit(reader, "trace-2", session_id="session-1", conversation_id="conversation-1", status="completed")

    result = search_traces(
        reader,
        TraceSearchQuery(schema_version="1", max_results=1),
        trace_ids=("trace-1", "trace-2"),
    )

    assert result.match_count == 1
    assert result.truncated is True
