from __future__ import annotations

from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
)
from packages.capability_runtime.fake import DeterministicFakeCapabilityAdapter


def test_fake_capability_proves_permission_dispatch_result_summary_without_raw_io() -> None:
    adapter = DeterministicFakeCapabilityAdapter()
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="fake.status"),
        proposed_action="fake_status",
        risk_level="low",
        arguments_schema={"type": "object"},
        raw_arguments_persisted=False,
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="decision-1",
        capability_ref=proposal.capability_ref,
        decision="approved",
        reason_code="test_allowlist",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )

    result, summary = adapter.dispatch(
        proposal=proposal,
        permission_decision=permission,
        arguments={"unsafe_raw_input": "should not be persisted"},
    )

    assert result.status == "succeeded"
    assert result.safe_result == {"status": "ok", "adapter": "deterministic_fake"}
    assert result.raw_input_persisted is False
    assert result.raw_output_persisted is False
    assert summary.executed_fake_capability_count == 1
    assert summary.safe_projection()["safe_result_status"] == "succeeded"
