from datetime import UTC, datetime

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import ConversationRef, TraceLevel, TraceStage
from packages.session_runtime import (
    CurrentProcessSessionRegistry,
    build_turn_linkage_from_assistant_turn_input,
)
from packages.telemetry import InMemoryTraceReader, make_trace_event


def test_assistant_turn_session_linkage_can_group_and_project_telemetry_refs():
    input_event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-session-integration",
        event_id="event-session-integration",
        text="raw text must stay out of session projections",
        timestamp=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        session_id="session-integration-001",
        metadata={"prompt": "raw prompt must not persist"},
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-session-integration",
        turn_id="turn-session-integration",
        input_event=input_event,
    )
    conversation_ref = ConversationRef(
        ref_type="conversation",
        ref_id="conversation-integration-001",
    )
    linkage = build_turn_linkage_from_assistant_turn_input(
        turn_input,
        conversation_ref=conversation_ref,
        previous_response_id="previous-response-secret",
    )
    registry = CurrentProcessSessionRegistry()
    registry.record_turn(linkage)

    reader = InMemoryTraceReader()
    reader.emit(
        make_trace_event(
            schema_version="0.1.1-draft",
            trace_id=linkage.trace_id,
            turn_id=linkage.turn_id,
            stage=TraceStage.TURN_COMPLETED,
            level=TraceLevel.INFO,
            message="Turn completed.",
            data=linkage.safe_projection(),
            timestamp=datetime(2026, 5, 17, 12, 1, tzinfo=UTC),
        )
    )

    session_projection = registry.read_session_projection(turn_input.session_ref)
    trace_projection = reader.read_trace("trace-session-integration")

    assert session_projection.safe_projection()["conversation_refs"] == [
        {"ref_type": "conversation", "ref_id": "conversation-integration-001"}
    ]
    event = trace_projection["events"][0]
    assert event["session_ref"] == {
        "ref_type": "session",
        "ref_id": "session-integration-001",
    }
    assert event["conversation_ref"] == {
        "ref_type": "conversation",
        "ref_id": "conversation-integration-001",
    }
    serialized = repr(session_projection.safe_projection()).lower() + repr(
        trace_projection
    ).lower()
    assert "raw text" not in serialized
    assert "raw prompt" not in serialized
    assert "previous-response-secret" not in serialized

