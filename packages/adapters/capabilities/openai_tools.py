from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import CapabilityCallProposal, CapabilityKind, CapabilityRef


class OpenAIToolAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenAIHostedToolRef(OpenAIToolAdapterModel):
    tool_type: str = Field(..., min_length=1)
    provider_owned: bool


class OpenAIRemoteMcpToolRef(OpenAIToolAdapterModel):
    server_label: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)


class OpenAIFunctionToolProposal(OpenAIToolAdapterModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    function_name: str = Field(..., min_length=1)
    json_schema: dict[str, object]
    hosted_tool_ref: OpenAIHostedToolRef | None = None
    remote_mcp_tool_ref: OpenAIRemoteMcpToolRef | None = None
    marvex_policy_transferred_to_openai: Literal[False] = False

    def to_capability_proposal(self) -> CapabilityCallProposal:
        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier=f"openai.{self.function_name}"),
            proposed_action=self.function_name,
            risk_level="medium",
            arguments_schema=self.json_schema,
            raw_arguments_persisted=False,
        )

class OpenAIToolSchemaDelivery(OpenAIToolAdapterModel):
    schema_version: str = Field(..., min_length=1)
    proposals: tuple[OpenAIFunctionToolProposal, ...]
    delivery_target: Literal["provider_schema", "tool_search_ready"]
    raw_schema_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "proposal_count": len(self.proposals),
            "delivery_target": self.delivery_target,
            "raw_schema_persisted": False,
        }
