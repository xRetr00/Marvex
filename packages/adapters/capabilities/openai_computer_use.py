from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import CapabilityKind


class OpenAIComputerUseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenAIComputerUseHarnessConfig(OpenAIComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    adapter_id: str = Field(..., min_length=1)
    responses_api_tool_type: Literal["computer", "computer_use_preview"] = "computer"
    legacy_responses_api_tool_type: Literal["computer_use_preview"] = "computer_use_preview"
    isolated_environment_required: Literal[True] = True
    screen_content_untrusted: Literal[True] = True
    openai_policy_transferred: Literal[False] = False
    raw_screen_persisted: Literal[False] = False

    def capability_kind(self) -> CapabilityKind:
        return CapabilityKind.TOOL

    def safe_projection(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "responses_api_tool_type": self.responses_api_tool_type,
            "legacy_responses_api_tool_type": self.legacy_responses_api_tool_type,
            "isolated_environment_required": True,
            "screen_content_untrusted": True,
            "openai_policy_transferred": False,
            "raw_screen_persisted": False,
        }
