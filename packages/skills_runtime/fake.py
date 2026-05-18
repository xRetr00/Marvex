from __future__ import annotations

from typing import Literal

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.skills_runtime.models import (
    SkillManifest,
    SkillPromptContribution,
    SkillRef,
    SkillResourceKind,
    SkillResourceRef,
    SkillValidationResult,
)


class DeterministicFakeSkillPackage(CapabilityRuntimeModel):
    manifest: SkillManifest
    test_only: Literal[True] = True

    @classmethod
    def summary_skill(cls) -> DeterministicFakeSkillPackage:
        skill_ref = SkillRef(skill_id="summary")
        contribution = SkillPromptContribution(
            schema_version="1",
            contribution_id="summary-context",
            skill_ref=skill_ref,
            summary="Summarize user-provided text into concise neutral bullets.",
            when_to_use="Use only when the user explicitly asks for summarization.",
            max_context_chars=320,
        )
        manifest = SkillManifest(
            schema_version="1",
            skill_ref=skill_ref,
            display_name="Summary Skill",
            description="Test-only deterministic skill package for summary context delivery.",
            instruction_ref=SkillResourceRef(kind=SkillResourceKind.INSTRUCTION, uri="local://skills/summary/SKILL.md"),
            resource_refs=(SkillResourceRef(kind=SkillResourceKind.RESOURCE, uri="local://skills/summary/templates/default.md"),),
            script_refs=(SkillResourceRef(kind=SkillResourceKind.SCRIPT_METADATA, uri="local://skills/summary/scripts/check.py"),),
            prompt_contributions=(contribution,),
        )
        return cls(manifest=manifest)

    def validate(self) -> SkillValidationResult:
        return SkillValidationResult.from_manifest(self.manifest)

    def safe_projection(self) -> dict[str, object]:
        projection = self.manifest.safe_projection()
        projection["test_only"] = True
        projection["script_execution_allowed"] = False
        return projection
