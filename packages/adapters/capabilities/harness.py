from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import CapabilityKind, CapabilityRef


class HarnessAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CapabilityHarnessRef(HarnessAdapterModel):
    harness_id: str = Field(..., min_length=1)


class CapabilityHarnessManifest(HarnessAdapterModel):
    schema_version: str = Field(..., min_length=1)
    harness_ref: CapabilityHarnessRef
    prompt_contribution_kinds: tuple[str, ...]
    context_delivery_ready: bool
    compaction_ready: bool
    verification_hook_ready: bool
    raw_prompt_persisted: Literal[False] = False

    def to_capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.HARNESS, identifier=f"harness.{self.harness_ref.harness_id}")

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "harness_id": self.harness_ref.harness_id,
            "prompt_contribution_count": len(self.prompt_contribution_kinds),
            "context_delivery_ready": self.context_delivery_ready,
            "compaction_ready": self.compaction_ready,
            "verification_hook_ready": self.verification_hook_ready,
            "raw_prompt_persisted": False,
        }
