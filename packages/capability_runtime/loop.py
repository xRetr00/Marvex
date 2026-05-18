from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from packages.capability_runtime.approvals import ApprovalDecision, CapabilityApprovalRequest, PendingApprovalState
from packages.capability_runtime.models import AgentLoopStopReason, CapabilityRef, CapabilityRuntimeModel, CapabilityStopReason
from packages.capability_runtime.proposals import CapabilityCallProposal
from packages.capability_runtime.requests import CapabilityExecutionRequest
from packages.capability_runtime.results import CapabilityResultEnvelope, make_denial_result
from packages.capability_runtime.models import CapabilityPermissionDecision


class CapabilityLoopGuard(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    loop_id: str = Field(..., min_length=1)
    max_steps: int = Field(..., ge=1, le=100)
    completed_steps: int = Field(..., ge=0)
    max_repeated_failures: int = Field(default=3, ge=1, le=20)
    repeated_failure_count: int = Field(default=0, ge=0)
    stop_reason: CapabilityStopReason = CapabilityStopReason.NOT_STOPPED
    pause_reason: str | None = None

    @property
    def stop_reason_effective(self) -> CapabilityStopReason:
        if self.stop_reason != CapabilityStopReason.NOT_STOPPED:
            return self.stop_reason
        if self.completed_steps >= self.max_steps:
            return CapabilityStopReason.MAX_STEPS_REACHED
        if self.repeated_failure_count >= self.max_repeated_failures:
            return CapabilityStopReason.REPEATED_FAILURES
        return CapabilityStopReason.NOT_STOPPED

    @property
    def should_stop(self) -> bool:
        return self.stop_reason_effective != CapabilityStopReason.NOT_STOPPED


class AgentLoopDecision(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    proposal: CapabilityCallProposal | None = None
    permission_decision: CapabilityPermissionDecision | None = None
    pending_approval: PendingApprovalState | None = None
    decision_kind: Literal["proposal", "pending_approval", "denied", "executed"]
    next_stop_reason: AgentLoopStopReason = AgentLoopStopReason.NOT_STOPPED
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def from_proposal(
        cls,
        *,
        decision_id: str,
        proposal: CapabilityCallProposal,
        permission_decision: CapabilityPermissionDecision,
    ) -> AgentLoopDecision:
        if permission_decision.capability_ref != proposal.capability_ref:
            raise ValueError("permission decision must match proposal capability_ref")
        stop_reason = (
            AgentLoopStopReason.POLICY_DENIED
            if permission_decision.decision == "denied"
            else AgentLoopStopReason.NOT_STOPPED
        )
        return cls(
            schema_version=proposal.schema_version,
            decision_id=decision_id,
            trace_id=proposal.trace_id,
            turn_id=proposal.turn_id,
            capability_ref=proposal.capability_ref,
            proposal=proposal,
            permission_decision=permission_decision,
            decision_kind="proposal",
            next_stop_reason=stop_reason,
        )

    @classmethod
    def from_pending_approval(
        cls,
        *,
        decision_id: str,
        proposal: CapabilityCallProposal,
        pending_approval: PendingApprovalState,
    ) -> AgentLoopDecision:
        if pending_approval.capability_ref != proposal.capability_ref:
            raise ValueError("pending approval must match proposal capability_ref")
        return cls(
            schema_version=proposal.schema_version,
            decision_id=decision_id,
            trace_id=proposal.trace_id,
            turn_id=proposal.turn_id,
            capability_ref=proposal.capability_ref,
            proposal=proposal,
            pending_approval=pending_approval,
            decision_kind="pending_approval",
            next_stop_reason=AgentLoopStopReason.WAITING_FOR_HUMAN_APPROVAL,
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "decision_kind": self.decision_kind,
            "next_stop_reason": self.next_stop_reason.value,
            "raw_payload_persisted": False,
        }


class AgentLoopStep(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    step_index: int = Field(..., ge=1)
    decision: AgentLoopDecision
    result_envelope: CapabilityResultEnvelope | None = None
    raw_payload_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_step_links(self) -> AgentLoopStep:
        if self.decision.trace_id != self.trace_id or self.decision.turn_id != self.turn_id:
            raise ValueError("agent loop step decision must match trace_id and turn_id")
        if self.result_envelope is not None and self.result_envelope.capability_ref != self.decision.capability_ref:
            raise ValueError("agent loop step result must match decision capability_ref")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "step_index": self.step_index,
            "decision": self.decision.safe_projection(),
            "result_status": self.result_envelope.status if self.result_envelope else None,
            "raw_payload_persisted": False,
        }


class SafeAgentLoopProjection(CapabilityRuntimeModel):
    schema_version: str
    loop_id: str
    trace_id: str
    turn_id: str
    step_count: int
    proposed_tool_count: int
    approved_count: int
    denied_count: int
    pending_approval_count: int
    executed_count: int
    stop_reason: str
    raw_payload_persisted: Literal[False] = False


class AgentLoopState(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    loop_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    max_steps: int = Field(..., ge=1, le=50)
    steps: tuple[AgentLoopStep, ...] = ()
    completed_steps: int = Field(default=0, ge=0)
    repeated_failure_count: int = Field(default=0, ge=0)
    max_repeated_failures: int = Field(default=3, ge=1, le=20)
    proposed_tool_count: int = Field(default=0, ge=0)
    approved_count: int = Field(default=0, ge=0)
    denied_count: int = Field(default=0, ge=0)
    pending_approval_count: int = Field(default=0, ge=0)
    executed_count: int = Field(default=0, ge=0)
    high_risk_pending_approval_count: int = Field(default=0, ge=0)
    stop_reason: AgentLoopStopReason = AgentLoopStopReason.NOT_STOPPED
    raw_payload_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_loop_state(self) -> AgentLoopState:
        if len(self.steps) > self.max_steps or self.completed_steps > self.max_steps:
            raise ValueError("agent loop state exceeds max_steps")
        for step in self.steps:
            if step.trace_id != self.trace_id or step.turn_id != self.turn_id:
                raise ValueError("agent loop steps must match loop trace_id and turn_id")
        return self

    def safe_projection(self) -> dict[str, object]:
        projection = SafeAgentLoopProjection(
            schema_version=self.schema_version,
            loop_id=self.loop_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            step_count=len(self.steps),
            proposed_tool_count=self.proposed_tool_count or len(self.steps),
            approved_count=self.approved_count,
            denied_count=self.denied_count,
            pending_approval_count=self.pending_approval_count,
            executed_count=self.executed_count,
            stop_reason=self.stop_reason.value,
        )
        return projection.model_dump()


class AgentLoopGuardResult(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    loop_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    should_stop: bool
    stop_reason: AgentLoopStopReason
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def human_approval_pause(
        cls,
        *,
        schema_version: str,
        loop_id: str,
        trace_id: str,
        turn_id: str,
    ) -> AgentLoopGuardResult:
        return cls(
            schema_version=schema_version,
            loop_id=loop_id,
            trace_id=trace_id,
            turn_id=turn_id,
            should_stop=True,
            stop_reason=AgentLoopStopReason.WAITING_FOR_HUMAN_APPROVAL,
        )


class ToolOrchestrationState(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    orchestration_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    proposal: CapabilityCallProposal
    permission_decision: CapabilityPermissionDecision | None = None
    approval_request: CapabilityApprovalRequest | None = None
    approval_decision: ApprovalDecision | None = None
    execution_request: CapabilityExecutionRequest | None = None
    result_envelope: CapabilityResultEnvelope | None = None
    provider_continuation_ready: bool = False
    final_response_ready: bool = False
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def denied(
        cls,
        *,
        orchestration_id: str,
        proposal: CapabilityCallProposal,
        approval_request: CapabilityApprovalRequest,
        approval_decision: ApprovalDecision,
        result_id: str,
    ) -> ToolOrchestrationState:
        return cls(
            schema_version=proposal.schema_version,
            orchestration_id=orchestration_id,
            trace_id=proposal.trace_id,
            turn_id=proposal.turn_id,
            proposal=proposal,
            approval_request=approval_request,
            approval_decision=approval_decision,
            result_envelope=make_denial_result(
                approval_request=approval_request,
                approval_decision=approval_decision,
                result_id=result_id,
            ),
        )

    @classmethod
    def executed(
        cls,
        *,
        orchestration_id: str,
        proposal: CapabilityCallProposal,
        permission_decision: CapabilityPermissionDecision,
        execution_request: CapabilityExecutionRequest,
        result_envelope: CapabilityResultEnvelope,
    ) -> ToolOrchestrationState:
        return cls(
            schema_version=proposal.schema_version,
            orchestration_id=orchestration_id,
            trace_id=proposal.trace_id,
            turn_id=proposal.turn_id,
            proposal=proposal,
            permission_decision=permission_decision,
            execution_request=execution_request,
            result_envelope=result_envelope,
            provider_continuation_ready=result_envelope.status == "succeeded",
            final_response_ready=result_envelope.status == "succeeded",
        )

    @model_validator(mode="after")
    def _validate_orchestration_links(self) -> ToolOrchestrationState:
        for item in (self.execution_request, self.result_envelope):
            if item is not None and (item.trace_id != self.trace_id or item.turn_id != self.turn_id):
                raise ValueError("tool orchestration linked items must match trace_id and turn_id")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "orchestration_id": self.orchestration_id,
            "capability_ref": self.proposal.capability_ref.safe_projection(),
            "permission_decision": self.permission_decision.decision if self.permission_decision else None,
            "approval_decision": self.approval_decision.decision if self.approval_decision else None,
            "pending_approval_count": 1 if self.approval_request is not None and self.approval_decision is None else 0,
            "execution_request_present": self.execution_request is not None,
            "result_status": self.result_envelope.status if self.result_envelope else None,
            "provider_continuation_ready": self.provider_continuation_ready,
            "final_response_ready": self.final_response_ready,
            "raw_payload_persisted": False,
        }


class ToolContinuationState(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    continuation_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    result_status: str
    provider_continuation_ready: bool
    raw_tool_output_persisted: Literal[False] = False

    @classmethod
    def from_result(
        cls,
        *,
        continuation_id: str,
        result: CapabilityResultEnvelope,
        provider_continuation_ready: bool,
    ) -> ToolContinuationState:
        return cls(
            schema_version=result.schema_version,
            continuation_id=continuation_id,
            trace_id=result.trace_id,
            turn_id=result.turn_id,
            capability_ref=result.capability_ref,
            result_status=result.status,
            provider_continuation_ready=provider_continuation_ready,
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "continuation_id": self.continuation_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "result_status": self.result_status,
            "provider_continuation_ready": self.provider_continuation_ready,
            "raw_tool_output_persisted": False,
        }


def evaluate_agent_loop_guard(state: AgentLoopState) -> AgentLoopGuardResult:
    if state.completed_steps >= state.max_steps:
        reason = AgentLoopStopReason.MAX_STEPS_REACHED
    elif state.repeated_failure_count >= state.max_repeated_failures:
        reason = AgentLoopStopReason.REPEATED_FAILURES
    else:
        reason = state.stop_reason
    return AgentLoopGuardResult(
        schema_version=state.schema_version,
        loop_id=state.loop_id,
        trace_id=state.trace_id,
        turn_id=state.turn_id,
        should_stop=reason != AgentLoopStopReason.NOT_STOPPED,
        stop_reason=reason,
    )
