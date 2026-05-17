from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from packages.capability_runtime.models import (
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityRuntimeModel,
    CapabilityStopReason,
)


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
    risk_level: Literal["low", "medium", "high"]
    arguments_schema: dict[str, Any]
    raw_arguments_persisted: Literal[False] = False


class CapabilityExecutionRequest(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    request_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    proposal: CapabilityCallProposal
    permission_decision: CapabilityPermissionDecision
    arguments: dict[str, Any]
    raw_arguments_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_permission(self) -> CapabilityExecutionRequest:
        if self.permission_decision.decision != "approved":
            raise ValueError("capability execution requires approved permission")
        if self.permission_decision.capability_ref != self.proposal.capability_ref:
            raise ValueError("permission decision must match proposal capability_ref")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "capability_ref": self.proposal.capability_ref.safe_projection(),
            "permission_decision": self.permission_decision.decision,
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
    stop_reason: CapabilityStopReason = CapabilityStopReason.NOT_STOPPED

    @property
    def should_stop(self) -> bool:
        return self.completed_steps >= self.max_steps or self.stop_reason != CapabilityStopReason.NOT_STOPPED


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
