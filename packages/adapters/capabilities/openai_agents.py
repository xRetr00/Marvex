from __future__ import annotations

import importlib.util
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


class OpenAIAgentsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenAIAgentsToolCompatibilityProposal(OpenAIAgentsModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    tool_schema: dict[str, object]
    agents_sdk_tool_present: bool = False
    agents_sdk_owns_execution: Literal[False] = False
    marvex_policy_authoritative: Literal[True] = True

    @classmethod
    def from_installed_sdk_tool(
        cls,
        *,
        schema_version: str,
        proposal_id: str,
        trace_id: str,
        turn_id: str,
        tool_name: str,
        tool_schema: dict[str, object],
    ) -> "OpenAIAgentsToolCompatibilityProposal":
        return cls(
            schema_version=schema_version,
            proposal_id=proposal_id,
            trace_id=trace_id,
            turn_id=turn_id,
            tool_name=tool_name,
            tool_schema=tool_schema,
            agents_sdk_tool_present=importlib.util.find_spec("agents") is not None,
        )

    def to_capability_proposal(self) -> CapabilityCallProposal:
        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier=f"openai_agents.{self.tool_name}"),
            proposed_action=self.tool_name,
            risk_level=ToolRiskLevel.MEDIUM,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
            arguments_schema=self.tool_schema,
            raw_arguments_persisted=False,
        )
