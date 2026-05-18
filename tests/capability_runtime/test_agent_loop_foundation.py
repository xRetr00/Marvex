from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.capability_runtime import (
    AgentLoopDecision,
    AgentLoopGuardResult,
    AgentLoopState,
    AgentLoopStep,
    AgentLoopStopReason,
    ApprovalDecision,
    ApprovalPrompt,
    CapabilityApprovalRequest,
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityResultEnvelope,
    HumanApprovalRequirement,
    PendingApprovalState,
    ToolContinuationState,
    ToolOrchestrationState,
    ToolRiskLevel,
    ToolSideEffectLevel,
    ToolingTelemetrySummary,
    evaluate_agent_loop_guard,
)


def _tool_ref(name: str = "builtin.calculator") -> CapabilityRef:
    return CapabilityRef(kind=CapabilityKind.TOOL, identifier=name)


def _proposal(*, risky: bool = False) -> CapabilityCallProposal:
    return CapabilityCallProposal(
        schema_version="1",
        proposal_id="proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=_tool_ref("browser.click" if risky else "builtin.calculator"),
        proposed_action="click" if risky else "calculator",
        risk_level=ToolRiskLevel.HIGH if risky else ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.BROWSER_ACTION if risky else ToolSideEffectLevel.READ_ONLY,
        execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL if risky else CapabilityExecutionMode.PROPOSAL_ONLY,
        arguments_schema={"type": "object"},
    )


def _permission(proposal: CapabilityCallProposal, *, decision: str = "approved") -> CapabilityPermissionDecision:
    return CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-1",
        capability_ref=proposal.capability_ref,
        decision=decision,
        reason_code="policy_allowlisted" if decision == "approved" else "policy_denied",
        human_approval=HumanApprovalRequirement(
            required=proposal.requires_approval,
            reason_code="approval_required" if proposal.requires_approval else "not_required",
            prompt_user_visible=proposal.requires_approval,
            risk_level=proposal.risk_level,
            side_effect_level=proposal.side_effect_level,
        ),
    )


def test_agent_loop_state_records_bounded_steps_and_safe_projection() -> None:
    proposal = _proposal()
    decision = AgentLoopDecision.from_proposal(
        decision_id="loop-decision-1",
        proposal=proposal,
        permission_decision=_permission(proposal),
    )
    step = AgentLoopStep(
        schema_version="1",
        step_id="step-1",
        trace_id="trace-1",
        turn_id="turn-1",
        step_index=1,
        decision=decision,
    )
    state = AgentLoopState(
        schema_version="1",
        loop_id="loop-1",
        trace_id="trace-1",
        turn_id="turn-1",
        max_steps=4,
        steps=(step,),
        stop_reason=AgentLoopStopReason.NOT_STOPPED,
    )
    projection = state.safe_projection()

    assert projection["step_count"] == 1
    assert projection["proposed_tool_count"] == 1
    assert projection["raw_payload_persisted"] is False

    with pytest.raises(ValidationError, match="exceeds max_steps"):
        AgentLoopState(
            schema_version="1",
            loop_id="loop-1",
            trace_id="trace-1",
            turn_id="turn-1",
            max_steps=1,
            steps=(
                step,
                AgentLoopStep(
                    schema_version="1",
                    step_id="step-2",
                    trace_id="trace-1",
                    turn_id="turn-1",
                    step_index=2,
                    decision=decision,
                ),
            ),
        )


def test_risky_tool_call_becomes_pending_approval_and_denial_is_safe() -> None:
    proposal = _proposal(risky=True)
    approval_request = CapabilityApprovalRequest(
        schema_version="1",
        approval_request_id="approval-request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=proposal.capability_ref,
        prompt=ApprovalPrompt(
            schema_version="1",
            prompt_id="approval-prompt-1",
            capability_ref=proposal.capability_ref,
            user_visible_summary="Allow browser click?",
            risk_level=proposal.risk_level,
            side_effect_level=proposal.side_effect_level,
        ),
    )
    pending = PendingApprovalState.from_request(approval_request)
    decision = AgentLoopDecision.from_pending_approval(
        decision_id="loop-decision-1",
        proposal=proposal,
        pending_approval=pending,
    )
    denial = ApprovalDecision(
        schema_version="1",
        decision_id="approval-denied-1",
        approval_request_id=approval_request.approval_request_id,
        capability_ref=proposal.capability_ref,
        decision="denied",
        decided_by="user",
    )
    result = ToolOrchestrationState.denied(
        orchestration_id="orchestration-1",
        proposal=proposal,
        approval_request=approval_request,
        approval_decision=denial,
        result_id="denied-result-1",
    )

    assert decision.next_stop_reason == AgentLoopStopReason.WAITING_FOR_HUMAN_APPROVAL
    assert result.result_envelope is not None
    assert result.result_envelope.status == "denied"
    assert result.safe_projection()["pending_approval_count"] == 0


def test_approved_safe_tool_execution_request_and_continuation_state_are_safe() -> None:
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
    result = CapabilityResultEnvelope(
        schema_version="1",
        result_id="result-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=proposal.capability_ref,
        status="succeeded",
        safe_result={"result_present": True},
    )
    orchestration = ToolOrchestrationState.executed(
        orchestration_id="orchestration-1",
        proposal=proposal,
        permission_decision=permission,
        execution_request=execution_request,
        result_envelope=result,
    )
    continuation = ToolContinuationState.from_result(
        continuation_id="continuation-1",
        result=result,
        provider_continuation_ready=True,
    )

    assert orchestration.execution_request is execution_request
    assert continuation.result_status == "succeeded"
    assert continuation.raw_tool_output_persisted is False
    assert continuation.safe_projection()["provider_continuation_ready"] is True


def test_loop_guard_result_stops_for_max_steps_repeated_failure_and_approval_pause() -> None:
    base_state = AgentLoopState(
        schema_version="1",
        loop_id="loop-1",
        trace_id="trace-1",
        turn_id="turn-1",
        max_steps=1,
        steps=(),
    )
    max_steps = evaluate_agent_loop_guard(base_state.model_copy(update={"completed_steps": 1}))
    repeated = evaluate_agent_loop_guard(base_state.model_copy(update={"repeated_failure_count": 3}))
    approval = AgentLoopGuardResult.human_approval_pause(
        schema_version="1",
        loop_id="loop-1",
        trace_id="trace-1",
        turn_id="turn-1",
    )

    assert max_steps.stop_reason == AgentLoopStopReason.MAX_STEPS_REACHED
    assert repeated.stop_reason == AgentLoopStopReason.REPEATED_FAILURES
    assert approval.stop_reason == AgentLoopStopReason.WAITING_FOR_HUMAN_APPROVAL


def test_tooling_telemetry_summary_from_loop_state_has_only_counts() -> None:
    state = AgentLoopState(
        schema_version="1",
        loop_id="loop-1",
        trace_id="trace-1",
        turn_id="turn-1",
        max_steps=4,
        steps=(),
        proposed_tool_count=2,
        approved_count=1,
        denied_count=1,
        executed_count=1,
        high_risk_pending_approval_count=0,
        stop_reason=AgentLoopStopReason.COMPLETED,
    )
    telemetry = ToolingTelemetrySummary.from_agent_loop_state(state)

    assert telemetry.tool_proposal_count == 2
    assert telemetry.executed_tool_count == 1
    assert telemetry.raw_tool_payloads_persisted is False
