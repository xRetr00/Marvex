from datetime import UTC, datetime

from packages.assistant_runtime import (
    AssistantStageName,
    build_text_input_event,
    build_turn_input_from_event,
    build_turn_lifecycle_summary,
)
from packages.contracts import ConversationRef, StageStatus, TraceEvent
from packages.memory_runtime import MemoryPolicyDecision, MemoryReadQuery, MemoryWriteCandidate
from packages.session_runtime import build_turn_linkage_from_assistant_turn_input


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def make_turn_input():
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-stage-life",
        event_id="event-stage-life",
        text="Hello lifecycle integration",
        timestamp=datetime(2026, 5, 17, 10, 0, tzinfo=UTC),
        session_id="session-stage-life",
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-stage-life",
        turn_id="turn-stage-life",
        input_event=event,
    )


def test_lifecycle_summary_links_existing_foundations_by_safe_reference_only():
    from packages.runtime_composition.assistant_provider_bridge import (
        run_fake_provider_assistant_bridge,
    )

    conversation_ref = ConversationRef(
        ref_type="conversation",
        ref_id="conversation-stage-life",
    )
    previous_response_id = "previous-stage-life-secret"
    turn_input = make_turn_input()
    linkage = build_turn_linkage_from_assistant_turn_input(
        turn_input,
        conversation_ref=conversation_ref,
        previous_response_id=previous_response_id,
    )
    read_query = MemoryReadQuery(
        schema_version="0.1.1-draft",
        query_id="memory-read-stage-life",
        scope="conversation",
        session_ref=None,
        conversation_ref=conversation_ref,
        max_records=5,
        policy_status="approved",
    )
    write_candidate = MemoryWriteCandidate(
        schema_version="0.1.1-draft",
        candidate_id="candidate-stage-life",
        scope="conversation",
        memory_kind="summary",
        session_ref=None,
        conversation_ref=conversation_ref,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        proposed_content="Safe future summary candidate.",
        source="manual",
        policy_status="pending",
    )
    policy_decision = MemoryPolicyDecision(
        schema_version="0.1.1-draft",
        candidate_id=write_candidate.candidate_id,
        decision="rejected",
        decided_by="explicit_user",
        reason_code="not-ready",
        approved_memory_ref=None,
    )
    sink = RecordingTelemetrySink()

    result = run_fake_provider_assistant_bridge(
        turn_input,
        model="fake-model",
        previous_response_id=previous_response_id,
        telemetry_sink=sink,
    )
    provider_ref = result.provider_turn_refs[0]
    summary = build_turn_lifecycle_summary(
        turn_input,
        result=result,
        conversation_ref=linkage.conversation_ref,
        previous_response_id=previous_response_id,
        provider_response_id=provider_ref.ref_id,
        memory_read_ready=read_query.policy_status == "approved",
        memory_read_ref_count=0,
        memory_write_candidate_ready=write_candidate.policy_status == "pending",
        memory_write_candidate_ref_count=1,
        memory_policy_decision_ref_count=1 if policy_decision.decision else 0,
        memory_forget_ready=False,
        telemetry_event_count=len(sink.events),
        persistent_trace_linked=True,
    )

    projection = summary.safe_projection()
    statuses = {
        stage.stage_name: stage.status for stage in summary.stage_results
    }

    assert projection["trace_id"] == "trace-stage-life"
    assert projection["turn_id"] == "turn-stage-life"
    assert projection["session_ref"] == {
        "ref_type": "session",
        "ref_id": "session-stage-life",
    }
    assert projection["conversation_ref"] == {
        "ref_type": "conversation",
        "ref_id": "conversation-stage-life",
    }
    assert projection["previous_response_id_present"] is True
    assert projection["provider_response_id_present"] is True
    assert projection["provider_turn_ref_count"] == 1
    assert projection["memory_read_ready"] is True
    assert projection["memory_write_candidate_ready"] is True
    assert projection["memory_policy_decision_ref_count"] == 1
    assert projection["telemetry_event_count"] == 5
    assert statuses[AssistantStageName.PROVIDER_RESULT_CONSUMPTION] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.MEMORY_READ_POLICY] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.MEMORY_WRITE_CANDIDATE] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.MEMORY_POLICY_HOOKS] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.TELEMETRY_TRACE_LINKAGE] == StageStatus.COMPLETED
    dumped = repr(projection)
    assert "Hello lifecycle integration" not in dumped
    assert "fake provider response" not in dumped
    assert previous_response_id not in dumped
    assert provider_ref.ref_id not in dumped
    assert "Safe future summary candidate" not in dumped
