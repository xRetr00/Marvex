from datetime import UTC, datetime

import pytest

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.assistant_runtime.result_assembly import build_text_success_turn_result
from packages.contracts import ConversationRef, ErrorCode, MemoryResultRef, StageStatus


def make_turn_input(*, session_id: str | None = "session-life"):
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-life",
        event_id="event-life",
        text="Hello lifecycle",
        timestamp=datetime(2026, 5, 17, 9, 0, tzinfo=UTC),
        session_id=session_id,
        metadata={"raw_prompt": "must not leak", "safe_key": "kept"},
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-life",
        turn_id="turn-life",
        input_event=event,
        metadata={"token": "must not leak", "safe": "kept"},
    )


def test_lifecycle_summary_links_safe_refs_and_presence_only():
    from packages.assistant_runtime import build_turn_lifecycle_summary

    result = build_text_success_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-life",
        turn_id="turn-life",
        text="Final text must not be stored in lifecycle.",
    ).model_copy(
        update={
            "memory_result_refs": [
                MemoryResultRef(ref_type="memory_result", ref_id="memory-result-life")
            ]
        }
    )
    summary = build_turn_lifecycle_summary(
        make_turn_input(),
        result=result,
        conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-life"),
        previous_response_id="previous-provider-response-secret",
        provider_response_id="provider-response-secret",
        memory_read_ready=True,
        memory_read_ref_count=2,
        memory_write_candidate_ready=True,
        memory_write_candidate_ref_count=1,
        memory_policy_decision_ref_count=1,
        memory_forget_ready=True,
        telemetry_event_count=5,
        persistent_trace_linked=True,
    )

    projection = summary.safe_projection()

    assert projection["session_ref"] == {
        "ref_type": "session",
        "ref_id": "session-life",
    }
    assert projection["conversation_ref"] == {
        "ref_type": "conversation",
        "ref_id": "conversation-life",
    }
    assert projection["previous_response_id_present"] is True
    assert projection["provider_response_id_present"] is True
    assert projection["provider_turn_ref_count"] == 0
    assert projection["memory_result_ref_count"] == 1
    assert projection["output_event_count"] == 0
    assert projection["memory_read_ready"] is True
    assert projection["memory_read_ref_count"] == 2
    assert projection["memory_write_candidate_ready"] is True
    assert projection["memory_write_candidate_ref_count"] == 1
    assert projection["memory_policy_decision_ref_count"] == 1
    assert projection["memory_forget_ready"] is True
    assert projection["telemetry_event_count"] == 5
    assert projection["persistent_trace_linked"] is True
    assert projection["transcript_persisted"] is False
    assert projection["raw_payload_persisted"] is False
    dumped = repr(summary.safe_projection())
    assert "Final text" not in dumped
    assert "previous-provider-response-secret" not in dumped
    assert "provider-response-secret" not in dumped
    assert "must not leak" not in dumped


def test_lifecycle_summary_records_expected_stage_statuses():
    from packages.assistant_runtime import AssistantStageName, build_turn_lifecycle_summary

    summary = build_turn_lifecycle_summary(
        make_turn_input(session_id=None),
        result=build_text_success_turn_result(
            schema_version="0.1.1-draft",
            trace_id="trace-life",
            turn_id="turn-life",
            text="Safe final text.",
        ),
        provider_response_id="provider-response-001",
    )

    statuses = {stage.stage_name: stage.status for stage in summary.stage_results}

    assert statuses[AssistantStageName.INPUT_NORMALIZATION] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.SESSION_CONVERSATION_LINKAGE] == StageStatus.SKIPPED
    assert statuses[AssistantStageName.RUNTIME_STATE_SNAPSHOT] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.MEMORY_READ_POLICY] == StageStatus.SKIPPED
    assert statuses[AssistantStageName.PROVIDER_STAGE_PREPARATION] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.PROVIDER_RESULT_CONSUMPTION] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.FINAL_RESPONSE_ASSEMBLY] == StageStatus.COMPLETED
    assert statuses[AssistantStageName.MEMORY_WRITE_CANDIDATE] == StageStatus.SKIPPED
    assert statuses[AssistantStageName.MEMORY_POLICY_HOOKS] == StageStatus.SKIPPED
    assert statuses[AssistantStageName.TELEMETRY_TRACE_LINKAGE] == StageStatus.SKIPPED


def test_lifecycle_summary_maps_provider_failure_without_provider_output():
    from packages.assistant_runtime import AssistantStageName, build_hard_failure_turn_result
    from packages.assistant_runtime import build_turn_lifecycle_summary

    result = build_hard_failure_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-life",
        turn_id="turn-life",
        error_id="turn-life:provider-stage",
        code=ErrorCode.PROVIDER_ERROR,
        message="Provider stage failed.",
    )

    summary = build_turn_lifecycle_summary(
        make_turn_input(),
        result=result,
        provider_response_id=None,
    )

    statuses = {stage.stage_name: stage.status for stage in summary.stage_results}
    projection = summary.safe_projection()

    assert statuses[AssistantStageName.PROVIDER_RESULT_CONSUMPTION] == StageStatus.FAILED
    assert statuses[AssistantStageName.FINAL_RESPONSE_ASSEMBLY] == StageStatus.FAILED
    assert projection["error_code"] == ErrorCode.PROVIDER_ERROR.value
    assert projection["provider_response_id_present"] is False
    assert "Provider stage failed" not in repr(projection)


def test_lifecycle_transition_validation_rejects_out_of_order_stage_changes():
    from packages.assistant_runtime import AssistantStageName, validate_lifecycle_transition

    assert validate_lifecycle_transition(
        AssistantStageName.INPUT_NORMALIZATION,
        AssistantStageName.PROVIDER_STAGE_PREPARATION,
    ) is True

    with pytest.raises(ValueError, match="must not move backwards"):
        validate_lifecycle_transition(
            AssistantStageName.FINAL_RESPONSE_ASSEMBLY,
            AssistantStageName.MEMORY_READ_POLICY,
        )


def test_lifecycle_rejects_negative_counts_and_mismatched_result_identity():
    from packages.assistant_runtime import build_turn_lifecycle_summary

    with pytest.raises(ValueError, match="must be non-negative"):
        build_turn_lifecycle_summary(
            make_turn_input(),
            memory_read_ref_count=-1,
        )

    mismatched_result = build_text_success_turn_result(
        schema_version="0.1.1-draft",
        trace_id="other-trace",
        turn_id="turn-life",
        text="Safe final text.",
    )

    with pytest.raises(ValueError, match="trace_id must match"):
        build_turn_lifecycle_summary(
            make_turn_input(),
            result=mismatched_result,
        )


def test_lifecycle_module_does_not_import_other_runtime_owner_packages():
    from pathlib import Path

    source = Path("packages/assistant_runtime/lifecycle.py").read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.local_api",
        "packages.runtime_composition",
        "packages.provider_runtime",
        "packages.memory_runtime",
        "packages.session_runtime",
        "packages.local_service_startup",
        "PersistentTraceStore",
    ]

    assert [term for term in forbidden if term in source] == []
