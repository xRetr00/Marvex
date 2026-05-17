from __future__ import annotations

from datetime import UTC, datetime

from packages.assistant_runtime.lifecycle import build_turn_lifecycle_summary
from packages.contracts import (
    AssistantMode,
    AssistantTurnInput,
    PolicyContext,
    Privacy,
    Sensitivity,
    SessionRef,
)


def test_lifecycle_summary_references_safe_capability_counts_without_execution() -> None:
    turn_input = AssistantTurnInput(
        schema_version="1",
        trace_id="trace-1",
        turn_id="turn-1",
        input_event_id="input-1",
        session_ref=SessionRef(ref_type="session", ref_id="session-1"),
        identity_ref=None,
        user_visible_input="summarize status",
        assistant_mode=AssistantMode.DEFAULT,
        policy_context=PolicyContext(requested_capabilities=[], sensitivity=Sensitivity.NORMAL),
        metadata={"timestamp": datetime.now(UTC).isoformat()},
    )

    summary = build_turn_lifecycle_summary(
        turn_input,
        capability_readiness_count=4,
        selected_eligible_capability_count=2,
        denied_capability_count=1,
        executed_fake_capability_count=1,
        capability_safe_result_status="succeeded",
    )

    projection = summary.safe_projection()

    assert projection["capability_readiness_count"] == 4
    assert projection["selected_eligible_capability_count"] == 2
    assert projection["denied_capability_count"] == 1
    assert projection["executed_fake_capability_count"] == 1
    assert projection["capability_safe_result_status"] == "succeeded"
    assert projection["raw_payload_persisted"] is False


