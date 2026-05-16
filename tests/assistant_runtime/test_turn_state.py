from datetime import UTC, datetime

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.assistant_runtime.result_assembly import (
    build_stage_summary,
    build_text_success_turn_result,
)
from packages.contracts import StageStatus


def make_turn_input(metadata=None, *, session_id=None):
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-state-test",
        event_id="event-state-test",
        text="Hello state",
        timestamp=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
        session_id=session_id,
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-state-test",
        turn_id="turn-state-test",
        input_event=event,
        metadata=metadata,
    )


def test_turn_state_snapshot_captures_one_turn_identity_without_transcript():
    from packages.assistant_runtime import build_turn_state_snapshot

    snapshot = build_turn_state_snapshot(
        make_turn_input(metadata={"prompt": "raw prompt", "safe": "kept"}),
        previous_response_id="previous-explicit",
    )

    assert snapshot.schema_version == "0.1.1-draft"
    assert snapshot.trace_id == "trace-state-test"
    assert snapshot.turn_id == "turn-state-test"
    assert snapshot.input_event_id == "event-state-test"
    assert snapshot.previous_response_id_present is True
    assert snapshot.user_visible_input_present is True
    assert snapshot.transcript_persisted is False
    assert snapshot.metadata_keys == ("[REDACTED]", "safe")
    assert "raw prompt" not in repr(snapshot)
    assert "previous-explicit" not in repr(snapshot)


def test_previous_response_id_is_explicit_only_not_read_from_metadata():
    from packages.assistant_runtime import build_turn_state_snapshot

    snapshot = build_turn_state_snapshot(
        make_turn_input(metadata={"previous_response_id": "hidden-response"}),
        previous_response_id=None,
    )

    assert snapshot.previous_response_id_present is False
    assert "hidden-response" not in snapshot.safe_projection().values()
    assert "hidden-response" not in repr(snapshot)


def test_turn_state_snapshot_tracks_session_readiness_without_session_body():
    from packages.assistant_runtime import build_turn_state_snapshot

    snapshot = build_turn_state_snapshot(
        make_turn_input(session_id="session-state-test"),
    )
    projection = snapshot.safe_projection()

    assert snapshot.session_ref_present is True
    assert projection["session_ref_present"] is True
    assert "session-state-test" not in repr(snapshot)
    assert "session-state-test" not in repr(projection)


def test_execution_summary_links_result_to_trace_turn_and_counts_refs_only():
    from packages.assistant_runtime import build_execution_summary

    result = build_text_success_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-state-test",
        turn_id="turn-state-test",
        text="Final answer text must not leak into state summary.",
        metadata={"raw_provider_output": "provider payload"},
    )

    summary = build_execution_summary(result)

    assert summary.trace_id == "trace-state-test"
    assert summary.turn_id == "turn-state-test"
    assert summary.completed is True
    assert summary.error_code is None
    assert summary.final_response_present is True
    assert summary.provider_ref_count == 0
    assert summary.tool_ref_count == 0
    assert summary.memory_ref_count == 0
    assert summary.stage_statuses == {
        "input_normalization": StageStatus.COMPLETED.value,
        "final_response_assembly": StageStatus.COMPLETED.value,
    }
    assert "Final answer text" not in repr(summary)
    assert "provider payload" not in repr(summary)


def test_execution_summary_redacts_unsafe_stage_names():
    from packages.assistant_runtime import build_execution_summary

    result = build_text_success_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-state-test",
        turn_id="turn-state-test",
        text="Safe final text.",
    ).model_copy(
        update={
            "stage_summaries": [
                build_stage_summary(
                    stage_name="raw provider output with secret token",
                    status=StageStatus.FAILED,
                )
            ]
        }
    )

    summary = build_execution_summary(result)

    assert summary.stage_statuses == {"[REDACTED]": StageStatus.FAILED.value}
    assert "secret token" not in repr(summary)


def test_state_transition_record_is_safe_and_ordered():
    from packages.assistant_runtime import StateTransitionRecord

    transition = StateTransitionRecord(
        schema_version="0.1.1-draft",
        trace_id="trace-state-test",
        turn_id="turn-state-test",
        sequence=1,
        from_state="input_received",
        to_state="provider_stage_ready",
        reason="input_validated",
    )

    assert transition.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-state-test",
        "turn_id": "turn-state-test",
        "sequence": 1,
        "from_state": "input_received",
        "to_state": "provider_stage_ready",
        "reason": "input_validated",
    }


def test_state_projection_rejects_sensitive_strings_and_raw_payload_keys():
    from packages.assistant_runtime import StateTransitionRecord

    transition = StateTransitionRecord(
        schema_version="0.1.1-draft",
        trace_id="trace-state-test",
        turn_id="turn-state-test",
        sequence=1,
        from_state="input_received",
        to_state="provider_stage_ready",
        reason="raw provider output included secret token",
    )

    projection = transition.safe_projection()

    assert projection["reason"] == "[REDACTED]"
    assert "secret token" not in repr(projection)


def test_state_module_does_not_import_runtime_owners_or_persistence():
    from pathlib import Path

    source = Path("packages/assistant_runtime/state.py").read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.local_api",
        "packages.runtime_composition",
        "packages.provider_runtime",
        "packages.telemetry",
        "packages.local_service_startup",
        "PersistentTraceStore",
    ]

    assert [term for term in forbidden if term in source] == []
