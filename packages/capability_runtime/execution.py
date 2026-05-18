from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from packages.capability_runtime.models import (
    AgentLoopStopReason,
    CapabilityEligibilityDecision,
    CapabilityExecutionMode,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityRuntimeModel,
    CapabilityStopReason,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


HIGH_IMPACT_SIDE_EFFECTS = {
    ToolSideEffectLevel.BROWSER_ACTION,
    ToolSideEffectLevel.DESKTOP_ACTION,
    ToolSideEffectLevel.CREDENTIAL_ACTION,
    ToolSideEffectLevel.PURCHASE_OR_PAYMENT,
    ToolSideEffectLevel.DESTRUCTIVE,
}


class CapabilityContextDeliveryPolicy(CapabilityRuntimeModel):
    max_capabilities: int = Field(..., ge=0, le=100)
    include_excluded_reasons: bool
    deliver_full_schema: bool = False


class CapabilityCompactionPolicy(CapabilityRuntimeModel):
    max_schema_bytes: int = Field(..., ge=1, le=100_000)
    offload_large_schemas: bool
    offload_ref_prefix: str = "local://capability-context/"


class CapabilityContextPack(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    delivery_policy: CapabilityContextDeliveryPolicy
    compaction_policy: CapabilityCompactionPolicy
    eligibility_decisions: tuple[Any, ...]
    prompt_contributions: tuple[str, ...] = ()

    def schema_delivery(self) -> dict[str, object]:
        eligible = [decision for decision in self.eligibility_decisions if decision.eligible]
        included = eligible[: self.delivery_policy.max_capabilities]
        excluded = [decision for decision in self.eligibility_decisions if not decision.eligible]
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "included_capabilities": [
                {
                    "identifier": decision.capability_ref.identifier,
                    "kind": decision.capability_ref.kind.value,
                    "reason_code": decision.reason_code,
                }
                for decision in included
            ],
            "excluded_capabilities": [
                {"identifier": decision.capability_ref.identifier, "reason_code": decision.reason_code}
                for decision in excluded
            ] if self.delivery_policy.include_excluded_reasons else [],
            "prompt_contributions": list(self.prompt_contributions),
            "all_capabilities_injected": False,
            "offload_large_schemas": self.compaction_policy.offload_large_schemas,
        }


class CapabilityCallProposal(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    proposed_action: str = Field(..., min_length=1)
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.READ_ONLY
    execution_mode: CapabilityExecutionMode = CapabilityExecutionMode.PROPOSAL_ONLY
    arguments_schema: dict[str, Any]
    raw_arguments_persisted: Literal[False] = False

    @property
    def requires_approval(self) -> bool:
        return self.side_effect_level in HIGH_IMPACT_SIDE_EFFECTS or self.execution_mode == CapabilityExecutionMode.REQUIRES_APPROVAL


class CapabilityExecutionRequest(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    request_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    proposal: CapabilityCallProposal
    permission_decision: CapabilityPermissionDecision
    approval_decision: ApprovalDecision | None = None
    arguments: dict[str, Any]
    execution_mode: CapabilityExecutionMode = CapabilityExecutionMode.APPROVED_EXECUTE
    raw_arguments_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_permission(self) -> CapabilityExecutionRequest:
        if self.permission_decision.decision != "approved":
            raise ValueError("capability execution requires approved permission")
        if self.permission_decision.capability_ref != self.proposal.capability_ref:
            raise ValueError("permission decision must match proposal capability_ref")
        if self.proposal.requires_approval:
            if self.approval_decision is None or self.approval_decision.decision != "approved":
                raise ValueError("risky capability execution requires approved human approval")
            if self.approval_decision.capability_ref != self.proposal.capability_ref:
                raise ValueError("approval decision must match proposal capability_ref")
        if self.execution_mode != CapabilityExecutionMode.APPROVED_EXECUTE:
            raise ValueError("capability execution request must use approved_execute mode")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "capability_ref": self.proposal.capability_ref.safe_projection(),
            "permission_decision": self.permission_decision.decision,
            "approval_decision": self.approval_decision.decision if self.approval_decision else None,
            "argument_keys": sorted(self.arguments),
            "raw_arguments_persisted": False,
        }


class CapabilityResultEnvelope(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    result_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    status: Literal["succeeded", "failed", "denied", "requires_human_approval"]
    safe_result: dict[str, Any]
    raw_input_persisted: Literal[False] = False
    raw_output_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "status": self.status,
            "safe_result_keys": sorted(self.safe_result),
            "raw_input_persisted": False,
            "raw_output_persisted": False,
        }


class CapabilityErrorEnvelope(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    error_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    code: str = Field(..., min_length=1)
    safe_message: str = Field(..., min_length=1)
    raw_error_persisted: Literal[False] = False


class CapabilityExecutionSummary(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    capability_readiness_count: int = Field(..., ge=0)
    selected_eligible_capability_count: int = Field(..., ge=0)
    denied_capability_count: int = Field(..., ge=0)
    executed_fake_capability_count: int = Field(..., ge=0)
    approved_count: int = Field(default=0, ge=0)
    high_risk_pending_approval_count: int = Field(default=0, ge=0)
    browser_action_count: int = Field(default=0, ge=0)
    computer_action_count: int = Field(default=0, ge=0)
    safe_result_status: str
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def from_result(
        cls,
        result: CapabilityResultEnvelope,
        *,
        readiness_count: int,
        eligible_count: int,
        denied_count: int,
        executed_fake_count: int,
    ) -> CapabilityExecutionSummary:
        return cls(
            schema_version=result.schema_version,
            trace_id=result.trace_id,
            turn_id=result.turn_id,
            capability_ref=result.capability_ref,
            capability_readiness_count=readiness_count,
            selected_eligible_capability_count=eligible_count,
            denied_capability_count=denied_count,
            executed_fake_capability_count=executed_fake_count,
            safe_result_status=result.status,
        )

    def safe_projection(self) -> dict[str, object]:
        return SafeCapabilityProjection.from_summary(self).model_dump()


class SafeCapabilityProjection(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    capability_readiness_count: int
    selected_eligible_capability_count: int
    denied_capability_count: int
    executed_fake_capability_count: int
    safe_result_status: str
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def from_summary(cls, summary: CapabilityExecutionSummary) -> SafeCapabilityProjection:
        return cls(
            schema_version=summary.schema_version,
            trace_id=summary.trace_id,
            turn_id=summary.turn_id,
            capability_readiness_count=summary.capability_readiness_count,
            selected_eligible_capability_count=summary.selected_eligible_capability_count,
            denied_capability_count=summary.denied_capability_count,
            executed_fake_capability_count=summary.executed_fake_capability_count,
            safe_result_status=summary.safe_result_status,
        )


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


# file size justification: CapabilityRuntime execution models intentionally keep approval, context delivery, loop guard, and result envelope primitives together while the foundation surface stabilizes.


class ApprovalPrompt(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    prompt_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    user_visible_summary: str = Field(..., min_length=1, max_length=500)
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    raw_prompt_persisted: Literal[False] = False


class ApprovalDecision(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    approval_request_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    decision: Literal["approved", "denied"]
    decided_by: Literal["user", "policy"]
    raw_decision_payload_persisted: Literal[False] = False


class CapabilityApprovalRequest(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    approval_request_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    prompt: ApprovalPrompt
    status: Literal["pending"] = "pending"
    raw_prompt_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_prompt_ref(self) -> CapabilityApprovalRequest:
        if self.prompt.capability_ref != self.capability_ref:
            raise ValueError("approval prompt must match approval request capability_ref")
        return self


class PendingApprovalState(CapabilityRuntimeModel):
    schema_version: str
    approval_request_id: str
    trace_id: str
    turn_id: str
    capability_ref: CapabilityRef
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    status: Literal["pending"] = "pending"
    raw_prompt_persisted: Literal[False] = False

    @classmethod
    def from_request(cls, request: CapabilityApprovalRequest) -> PendingApprovalState:
        return cls(
            schema_version=request.schema_version,
            approval_request_id=request.approval_request_id,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            capability_ref=request.capability_ref,
            risk_level=request.prompt.risk_level,
            side_effect_level=request.prompt.side_effect_level,
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "approval_request_id": self.approval_request_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "risk_level": self.risk_level.value,
            "side_effect_level": self.side_effect_level.value,
            "status": self.status,
            "raw_prompt_persisted": False,
        }


class ToolExecutionPolicy(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    policy_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    execution_mode: CapabilityExecutionMode
    human_approval: Any
    raw_policy_payload_persisted: Literal[False] = False

    @property
    def requires_human_approval(self) -> bool:
        return (
            self.risk_level in {ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL}
            or self.side_effect_level in HIGH_IMPACT_SIDE_EFFECTS
            or self.execution_mode == CapabilityExecutionMode.REQUIRES_APPROVAL
        )

    @model_validator(mode="after")
    def _validate_approval(self) -> ToolExecutionPolicy:
        if self.requires_human_approval and not self.human_approval.required:
            raise ValueError("risky tool policy requires human approval")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "risk_level": self.risk_level.value,
            "side_effect_level": self.side_effect_level.value,
            "execution_mode": self.execution_mode.value,
            "requires_human_approval": self.requires_human_approval,
            "raw_policy_payload_persisted": False,
        }


class CapabilityToolContextDelivery(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    manifests: tuple[Any, ...]
    eligibility_decisions: tuple[CapabilityEligibilityDecision, ...]
    delivery_policy: CapabilityContextDeliveryPolicy
    compaction_policy: CapabilityCompactionPolicy

    def schema_delivery(self) -> dict[str, object]:
        eligible_refs = {
            decision.capability_ref
            for decision in self.eligibility_decisions
            if decision.eligible
        }
        included = [manifest for manifest in self.manifests if manifest.capability_ref in eligible_refs]
        included = included[: self.delivery_policy.max_capabilities]
        included_ids = {manifest.capability_ref.identifier for manifest in included}
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "included_tools": [manifest.capability_ref.identifier for manifest in included],
            "excluded_tools": [
                manifest.capability_ref.identifier
                for manifest in self.manifests
                if manifest.capability_ref.identifier not in included_ids
            ],
            "all_tools_injected": False,
            "raw_schema_persisted": False,
        }


class ToolingTelemetrySummary(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    tool_proposal_count: int = Field(..., ge=0)
    approved_count: int = Field(..., ge=0)
    denied_count: int = Field(..., ge=0)
    executed_tool_count: int = Field(..., ge=0)
    browser_action_count: int = Field(..., ge=0)
    computer_action_count: int = Field(..., ge=0)
    high_risk_pending_approval_count: int = Field(..., ge=0)
    raw_tool_payloads_persisted: Literal[False] = False
    raw_browser_payload_persisted: Literal[False] = False
    raw_screenshots_persisted: Literal[False] = False

    @classmethod
    def from_agent_loop_state(cls, state: AgentLoopState) -> ToolingTelemetrySummary:
        return cls(
            schema_version=state.schema_version,
            trace_id=state.trace_id,
            turn_id=state.turn_id,
            tool_proposal_count=state.proposed_tool_count,
            approved_count=state.approved_count,
            denied_count=state.denied_count,
            executed_tool_count=state.executed_count,
            browser_action_count=0,
            computer_action_count=0,
            high_risk_pending_approval_count=state.high_risk_pending_approval_count,
        )

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump()


def make_denial_result(
    *,
    approval_request: CapabilityApprovalRequest,
    approval_decision: ApprovalDecision,
    result_id: str,
) -> CapabilityResultEnvelope:
    if approval_decision.decision != "denied":
        raise ValueError("denial result requires denied approval decision")
    if approval_decision.capability_ref != approval_request.capability_ref:
        raise ValueError("approval decision must match approval request capability_ref")
    return CapabilityResultEnvelope(
        schema_version=approval_request.schema_version,
        result_id=result_id,
        trace_id=approval_request.trace_id,
        turn_id=approval_request.turn_id,
        capability_ref=approval_request.capability_ref,
        status="denied",
        safe_result={"approval_decision": "denied"},
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


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


class PlanStep(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    plan_ref: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    required_capability_refs: tuple[CapabilityRef, ...] = ()


class TaskDecompositionHint(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    hint_id: str = Field(..., min_length=1)
    parent_task_ref: str = Field(..., min_length=1)
    suggested_steps: tuple[PlanStep, ...]
    autonomous_execution_allowed: Literal[False] = False


class VerificationHook(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    hook_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    required: bool
    reason_code: str = Field(..., min_length=1)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "hook_id": self.hook_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "required": self.required,
            "reason_code": self.reason_code,
        }
