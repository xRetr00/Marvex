from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from packages.capability_runtime.models import CapabilityExecutionMode, CapabilityRef, CapabilityRuntimeModel, ToolRiskLevel, ToolSideEffectLevel
from packages.capability_runtime.proposals import HIGH_IMPACT_SIDE_EFFECTS


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
