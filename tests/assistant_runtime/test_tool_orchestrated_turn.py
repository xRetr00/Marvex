from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.adapters.capabilities.builtins import BuiltinToolCatalog
from packages.assistant_runtime.tool_orchestration import (
    ToolOrchestratedTurnState,
    build_tool_orchestrated_lifecycle_summary,
)
from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionRequest,
    CapabilityExecutionMode,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from packages.contracts import AssistantTurnInput


def _turn_input() -> AssistantTurnInput:
    event = build_text_input_event(
        schema_version="1",
        trace_id="trace-1",
        event_id="input-1",
        text="calculate 2+2",
        timestamp=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
        session_id="session-1",
    )
    return build_turn_input_from_event(
        schema_version="1",
        trace_id="trace-1",
        turn_id="turn-1",
        input_event=event,
    )


def _proposal() -> CapabilityCallProposal:
    return CapabilityCallProposal(
        schema_version="1",
        proposal_id="proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"),
        proposed_action="calculator",
        risk_level=ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
        arguments_schema={"type": "object"},
    )


def _permission(proposal: CapabilityCallProposal) -> CapabilityPermissionDecision:
    return CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-1",
        capability_ref=proposal.capability_ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )


def test_tool_orchestrated_turn_models_provider_proposal_to_final_readiness() -> None:
    proposal = _proposal()
    permission = _permission(proposal)
    execution_request = CapabilityExecutionRequest(
        schema_version="1",
        request_id="request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        proposal=proposal,
        permission_decision=permission,
        arguments={"expression": "2 + 2"},
    )
    result = BuiltinToolCatalog.default().execute_request(execution_request).result
    state = ToolOrchestratedTurnState.from_safe_result(
        turn_input=_turn_input(),
        eligible_capability_count=1,
        proposal=proposal,
        permission_decision=permission,
        result=result,
        continuation_id="continuation-1",
    )
    summary = build_tool_orchestrated_lifecycle_summary(_turn_input(), state)
    projection = state.safe_projection()

    assert projection["provider_tool_proposal_count"] == 1
    assert projection["provider_continuation_ready"] is True
    assert projection["final_response_ready"] is True
    assert projection["raw_payload_persisted"] is False
    assert summary.capability_safe_result_status == "succeeded"
    assert summary.safe_projection()["agent_loop_step_count"] == 1

def test_tool_orchestrated_turn_rejects_trace_mismatch_and_does_not_import_adapters() -> None:
    proposal = _proposal().model_copy(update={"trace_id": "other-trace"})

    with pytest.raises(ValueError, match="trace_id must match"):
        ToolOrchestratedTurnState.from_provider_proposal(
            turn_input=_turn_input(),
            eligible_capability_count=1,
            proposal=proposal,
        )
