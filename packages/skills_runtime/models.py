from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from packages.capability_runtime import CapabilityKind, CapabilityManifest, CapabilityRef
from packages.capability_runtime.models import CapabilityRuntimeModel

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_POLICY_OVERRIDE_MARKERS = (
    "ignore previous instructions",
    "ignore system instructions",
    "override system prompt",
    "override the system prompt",
    "override marvex policy",
    "reveal hidden policy",
    "bypass policy",
    "developer message",
    "system prompt",
)


class SkillResourceKind(str, Enum):
    INSTRUCTION = "instruction"
    RESOURCE = "resource"
    SCRIPT_METADATA = "script_metadata"


class SkillRef(CapabilityRuntimeModel):
    skill_id: str = Field(..., min_length=1)

    @field_validator("skill_id")
    @classmethod
    def _validate_skill_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("skill_id must be non-empty and trimmed")
        if any(character not in _SAFE_ID_CHARS for character in value):
            raise ValueError("skill_id must contain only safe id characters")
        return value

    def to_capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.SKILL, identifier=f"skill.{self.skill_id}")


class SkillResourceRef(CapabilityRuntimeModel):
    kind: SkillResourceKind
    uri: str = Field(..., min_length=1)
    content_digest: str | None = None
    raw_content_persisted: Literal[False] = False

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        if not value.startswith("local://skills/"):
            raise ValueError("skill manifests may reference only local skill resources")
        if ".." in value or "\\" in value:
            raise ValueError("skill resource uri must stay within local skill resources")
        return value


class SkillPromptContribution(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    contribution_id: str = Field(..., min_length=1)
    skill_ref: SkillRef
    summary: str = Field(..., min_length=1, max_length=600)
    when_to_use: str = Field(..., min_length=1, max_length=400)
    max_context_chars: int = Field(..., ge=1, le=1200)
    can_override_system_policy: Literal[False] = False
    raw_instruction_persisted: Literal[False] = False

    @field_validator("contribution_id")
    @classmethod
    def _validate_contribution_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("contribution_id must be non-empty and trimmed")
        if any(character not in _SAFE_ID_CHARS for character in value):
            raise ValueError("contribution_id must contain only safe id characters")
        return value

    @field_validator("summary", "when_to_use")
    @classmethod
    def _reject_policy_override(cls, value: str) -> str:
        lowered = value.lower()
        if any(marker in lowered for marker in _POLICY_OVERRIDE_MARKERS):
            raise ValueError("skill prompt contribution cannot override Marvex policy")
        return value

    def as_bounded_context(self) -> str:
        context = f"Skill {self.skill_ref.skill_id}: {self.summary} Use when: {self.when_to_use}"
        return context[: self.max_context_chars]

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "contribution_id": self.contribution_id,
            "skill_ref": self.skill_ref.to_capability_ref().safe_projection(),
            "summary_chars": len(self.summary),
            "when_to_use_chars": len(self.when_to_use),
            "max_context_chars": self.max_context_chars,
            "raw_instruction_persisted": False,
        }


class SkillManifest(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    skill_ref: SkillRef
    display_name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    instruction_ref: SkillResourceRef
    resource_refs: tuple[SkillResourceRef, ...] = ()
    script_refs: tuple[SkillResourceRef, ...] = ()
    prompt_contributions: tuple[SkillPromptContribution, ...] = ()
    can_override_system_policy: Literal[False] = False
    arbitrary_script_execution_allowed: Literal[False] = False
    arbitrary_install_allowed: Literal[False] = False
    remote_loading_allowed: Literal[False] = False
    raw_instruction_persisted: Literal[False] = False
    raw_prompt_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_manifest(self) -> SkillManifest:
        for value in (self.display_name, self.description):
            lowered = value.lower()
            if any(marker in lowered for marker in _POLICY_OVERRIDE_MARKERS):
                raise ValueError("skill manifest cannot override Marvex policy")
        if self.instruction_ref.kind != SkillResourceKind.INSTRUCTION:
            raise ValueError("instruction_ref must use instruction resource kind")
        for resource in self.resource_refs:
            if resource.kind != SkillResourceKind.RESOURCE:
                raise ValueError("resource_refs must use resource kind")
        for script in self.script_refs:
            if script.kind != SkillResourceKind.SCRIPT_METADATA:
                raise ValueError("script_refs are script metadata only")
        for contribution in self.prompt_contributions:
            if contribution.skill_ref != self.skill_ref:
                raise ValueError("skill prompt contributions must match manifest skill_ref")
        return self

    def to_capability_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            schema_version=self.schema_version,
            capability_ref=self.skill_ref.to_capability_ref(),
            display_name=self.display_name,
            description=self.description,
            owner_package="packages.skills_runtime",
            adapter_boundary="skills_runtime_foundation",
            permissions=(f"skill.{self.skill_ref.skill_id}.context",),
            metadata={
                "runtime_owner": "packages.skills_runtime",
                "skill_not_tool": True,
                "script_execution_allowed": False,
                "remote_loading_allowed": False,
                "arbitrary_install_allowed": False,
                "prompt_contribution_count": len(self.prompt_contributions),
            },
            enabled_by_default=False,
        )

    def safe_projection(self) -> dict[str, object]:
        return SafeSkillProjection.from_manifest(self).model_dump()


class SafeSkillProjection(CapabilityRuntimeModel):
    schema_version: str
    skill_ref: dict[str, str]
    display_name: str
    resource_count: int
    script_count: int
    prompt_contribution_count: int
    can_override_system_policy: Literal[False] = False
    script_execution_allowed: Literal[False] = False
    arbitrary_install_allowed: Literal[False] = False
    remote_loading_allowed: Literal[False] = False
    raw_instruction_persisted: Literal[False] = False
    raw_prompt_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def from_manifest(cls, manifest: SkillManifest) -> SafeSkillProjection:
        return cls(
            schema_version=manifest.schema_version,
            skill_ref=manifest.skill_ref.to_capability_ref().safe_projection(),
            display_name=manifest.display_name,
            resource_count=len(manifest.resource_refs),
            script_count=len(manifest.script_refs),
            prompt_contribution_count=len(manifest.prompt_contributions),
        )


class SkillValidationResult(CapabilityRuntimeModel):
    schema_version: str
    skill_ref: SkillRef
    valid: bool
    reason_codes: tuple[str, ...]
    safe_instruction_present: bool
    prompt_contribution_count: int
    prompt_contributions: tuple[str, ...] = ()
    policy_override_detected: bool = False
    script_execution_allowed: Literal[False] = False
    arbitrary_install_allowed: Literal[False] = False
    remote_loading_allowed: Literal[False] = False

    @classmethod
    def from_manifest(cls, manifest: SkillManifest) -> SkillValidationResult:
        reason_codes = ("valid",) if manifest.prompt_contributions else ("valid", "no_prompt_contribution")
        prompt_contributions = tuple(
            contribution.as_bounded_context()
            for contribution in manifest.prompt_contributions
        )
        return cls(
            schema_version=manifest.schema_version,
            skill_ref=manifest.skill_ref,
            valid=True,
            reason_codes=reason_codes,
            safe_instruction_present=True,
            prompt_contribution_count=len(manifest.prompt_contributions),
            prompt_contributions=prompt_contributions,
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "skill_ref": self.skill_ref.to_capability_ref().safe_projection(),
            "valid": self.valid,
            "reason_codes": list(self.reason_codes),
            "prompt_contribution_count": self.prompt_contribution_count,
            "policy_override_detected": self.policy_override_detected,
            "script_execution_allowed": False,
            "arbitrary_install_allowed": False,
            "remote_loading_allowed": False,
        }
