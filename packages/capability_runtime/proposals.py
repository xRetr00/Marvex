from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityExecutionMode, CapabilityRef, CapabilityRuntimeModel, ToolRiskLevel, ToolSideEffectLevel

HIGH_IMPACT_SIDE_EFFECTS = {
    ToolSideEffectLevel.BROWSER_ACTION,
    ToolSideEffectLevel.DESKTOP_ACTION,
    ToolSideEffectLevel.CREDENTIAL_ACTION,
    ToolSideEffectLevel.PURCHASE_OR_PAYMENT,
    ToolSideEffectLevel.DESTRUCTIVE,
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
