from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.capability_runtime import CapabilityEligibilityDecision, CapabilityKind, CapabilityRef


class SkillAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SkillRef(SkillAdapterModel):
    skill_id: str = Field(..., min_length=1)

    def to_capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.SKILL, identifier=f"skill.{self.skill_id}")


class SkillManifest(SkillAdapterModel):
    schema_version: str = Field(..., min_length=1)
    skill_ref: SkillRef
    instruction_uri: str = Field(..., min_length=1)
    resource_uris: tuple[str, ...] = ()
    script_uris: tuple[str, ...] = ()
    can_override_system_policy: Literal[False] = False
    arbitrary_script_execution_allowed: Literal[False] = False

    @field_validator("instruction_uri", "resource_uris", "script_uris")
    @classmethod
    def _validate_local_uri(cls, value):
        values = value if isinstance(value, tuple) else (value,)
        for uri in values:
            if not str(uri).startswith("local://"):
                raise ValueError("skill manifest URIs must be local references")
        return value


class SkillValidationResult(SkillAdapterModel):
    schema_version: str
    skill_ref: SkillRef
    valid: bool
    safe_instruction_present: bool
    script_execution_allowed: Literal[False] = False

    @classmethod
    def from_manifest(cls, manifest: SkillManifest) -> SkillValidationResult:
        return cls(
            schema_version=manifest.schema_version,
            skill_ref=manifest.skill_ref,
            valid=True,
            safe_instruction_present=True,
            script_execution_allowed=False,
        )


class SkillEligibilityDecision(SkillAdapterModel):
    decision: CapabilityEligibilityDecision
    prompt_contribution: str | None = None

    @model_validator(mode="after")
    def _validate_skill_ref(self) -> SkillEligibilityDecision:
        if self.decision.capability_ref.kind != CapabilityKind.SKILL:
            raise ValueError("skill eligibility must reference a skill capability")
        return self
