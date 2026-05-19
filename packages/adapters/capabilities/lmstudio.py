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


class LMStudioAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LMStudioMcpHostRef(LMStudioAdapterModel):
    host_id: str = Field(..., min_length=1)
    api_surface: Literal["local_server", "app_host_reference"]


class LMStudioLocalToolProposal(LMStudioAdapterModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    tool_name_status: Literal["safe", "unsafe"] = "safe"
    original_tool_name_persisted: Literal[False] = False
    mcp_host_ref: LMStudioMcpHostRef | None = None
    marvex_policy_authoritative: bool
    lmstudio_owns_tool_hosting: Literal[False] = False

    def to_capability_proposal(self) -> CapabilityCallProposal:
        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier=f"lmstudio.{self.tool_name}"),
            proposed_action="blocked_provider_tool" if self.tool_name_status == "unsafe" else self.tool_name,
            risk_level=ToolRiskLevel.MEDIUM,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )
