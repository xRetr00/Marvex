from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import CapabilityRef


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
