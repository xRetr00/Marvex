from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityKind,
    CapabilityRef,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class LiteLLMGatewayAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LiteLLMToolsetRef(LiteLLMGatewayAdapterModel):
    toolset_id: str = Field(..., min_length=1)
    external_permission_source: str = Field(..., min_length=1)


class LiteLLMToolsetProjection(LiteLLMGatewayAdapterModel):
    schema_version: str = Field(..., min_length=1)
    toolset_ref: LiteLLMToolsetRef
    listed_capability_refs: tuple[CapabilityRef, ...]
    marvex_policy_authoritative: bool
    raw_gateway_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "toolset_id": self.toolset_ref.toolset_id,
            "listed_capability_count": len(self.listed_capability_refs),
            "marvex_policy_authoritative": self.marvex_policy_authoritative,
            "raw_gateway_payload_persisted": False,
        }


class LiteLLMToolCallProposal(LiteLLMGatewayAdapterModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    toolset_ref: LiteLLMToolsetRef
    litellm_owns_execution: Literal[False] = False
    marvex_policy_authoritative: Literal[True] = True

    def to_capability_proposal(self) -> CapabilityCallProposal:
        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier=f"litellm.{self.tool_name}"),
            proposed_action=self.tool_name,
            risk_level=ToolRiskLevel.MEDIUM,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )
