from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from packages.capability_runtime.approvals import ApprovalDecision
from packages.capability_runtime.models import CapabilityExecutionMode, CapabilityPermissionDecision, CapabilityRuntimeModel
from packages.capability_runtime.proposals import CapabilityCallProposal


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
