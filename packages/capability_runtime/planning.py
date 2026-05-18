from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRef, CapabilityRuntimeModel


class PlanStep(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    plan_ref: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    required_capability_refs: tuple[CapabilityRef, ...] = ()


class TaskDecompositionHint(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    hint_id: str = Field(..., min_length=1)
    parent_task_ref: str = Field(..., min_length=1)
    suggested_steps: tuple[PlanStep, ...]
    autonomous_execution_allowed: Literal[False] = False


class VerificationHook(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    hook_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    required: bool
    reason_code: str = Field(..., min_length=1)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "hook_id": self.hook_id,
            "capability_ref": self.capability_ref.safe_projection(),
            "required": self.required,
            "reason_code": self.reason_code,
        }
