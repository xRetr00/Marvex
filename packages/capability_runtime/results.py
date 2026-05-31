from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.capability_runtime.approvals import ApprovalDecision, CapabilityApprovalRequest
from packages.capability_runtime.models import CapabilityRef, CapabilityRuntimeModel


class CapabilityResultEnvelope(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    result_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    status: Literal["succeeded", "failed", "denied", "requires_human_approval"]
    safe_result: dict[str, Any]
    raw_input_persisted: bool = False
    raw_output_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "status": self.status,
            "safe_result_keys": sorted(self.safe_result),
            "raw_input_persisted": self.raw_input_persisted,
            "raw_output_persisted": self.raw_output_persisted,
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
    raw_payload_persisted: bool = False

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
            raw_payload_persisted=bool(result.raw_input_persisted or result.raw_output_persisted),
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
    raw_payload_persisted: bool = False

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
            raw_payload_persisted=summary.raw_payload_persisted,
        )


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
