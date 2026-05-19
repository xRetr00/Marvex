from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from packages.capability_runtime import (
    CapabilityCompactionPolicy,
    CapabilityContextDeliveryPolicy,
    CapabilityContextPack,
    CapabilityEligibilityDecision,
    CapabilityKind,
    CapabilityRef,
)
from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.skills_runtime.models import SkillManifest, SkillValidationResult


class SkillEligibilityDecision(CapabilityRuntimeModel):
    manifest: SkillManifest | None = None
    validation: SkillValidationResult
    decision: CapabilityEligibilityDecision
    prompt_contributions_delivered: tuple[str, ...] = ()
    raw_prompt_persisted: Literal[False] = False

    @classmethod
    def from_validation(
        cls,
        validation: SkillValidationResult,
        *,
        decision_id: str,
        eligible: bool,
        reason_code: str,
        intent_tags: tuple[str, ...] = (),
        manifest: SkillManifest | None = None,
    ) -> SkillEligibilityDecision:
        decision = CapabilityEligibilityDecision(
            schema_version=validation.schema_version,
            decision_id=decision_id,
            capability_ref=validation.skill_ref.to_capability_ref(),
            eligible=eligible and validation.valid,
            reason_code=reason_code,
            intent_tags=intent_tags,
        )
        contributions = validation.prompt_contributions if decision.eligible else ()
        return cls(
            manifest=manifest,
            validation=validation,
            decision=decision,
            prompt_contributions_delivered=contributions,
        )

    @model_validator(mode="after")
    def _validate_skill_decision(self) -> SkillEligibilityDecision:
        if self.decision.capability_ref.kind != CapabilityKind.SKILL:
            raise ValueError("skill eligibility must reference a skill capability")
        if self.decision.capability_ref != self.validation.skill_ref.to_capability_ref():
            raise ValueError("skill eligibility decision must match validation skill_ref")
        if self.manifest is not None and self.validation.skill_ref != self.manifest.skill_ref:
            raise ValueError("skill validation must match manifest skill_ref")
        return self

    @property
    def eligible(self) -> bool:
        return self.decision.eligible

    @property
    def capability_ref(self) -> CapabilityRef:
        return self.decision.capability_ref

    @property
    def reason_code(self) -> str:
        return self.decision.reason_code

    @property
    def intent_tags(self) -> tuple[str, ...]:
        return self.decision.intent_tags

    def safe_projection(self) -> dict[str, object]:
        return {
            "skill_ref": self.validation.skill_ref.to_capability_ref().safe_projection(),
            "eligible": self.decision.eligible,
            "reason_code": self.decision.reason_code,
            "prompt_contribution_count": len(self.prompt_contributions_delivered),
            "raw_prompt_persisted": False,
        }


def build_skill_context_pack(
    *,
    trace_id: str,
    turn_id: str,
    skill_decisions: tuple[SkillEligibilityDecision, ...],
    delivery_policy: CapabilityContextDeliveryPolicy,
    compaction_policy: CapabilityCompactionPolicy,
) -> CapabilityContextPack:
    included = [decision for decision in skill_decisions if decision.eligible]
    included = included[: delivery_policy.max_capabilities]
    prompt_contributions: list[str] = []
    for decision in included:
        prompt_contributions.extend(decision.prompt_contributions_delivered)
    return CapabilityContextPack(
        schema_version="1",
        trace_id=trace_id,
        turn_id=turn_id,
        delivery_policy=delivery_policy,
        compaction_policy=compaction_policy,
        eligibility_decisions=tuple(decision.decision for decision in skill_decisions),
        prompt_contributions=tuple(prompt_contributions),
    )


def select_skills_for_intent(
    *,
    intent_kind: object,
    context_terms: tuple[str, ...],
    manifests: tuple[SkillManifest, ...],
) -> tuple[SkillEligibilityDecision, ...]:
    intent_value = getattr(intent_kind, "value", str(intent_kind))
    terms = {intent_value.replace("_", " "), intent_value}
    terms.update(term.lower() for term in context_terms)
    decisions: list[SkillEligibilityDecision] = []
    for index, manifest in enumerate(manifests, start=1):
        validation = SkillValidationResult.from_manifest(manifest)
        searchable = " ".join([manifest.display_name, manifest.description, " ".join(contribution.when_to_use for contribution in manifest.prompt_contributions)]).lower()
        eligible = any(term and term in searchable for term in terms)
        decisions.append(
            SkillEligibilityDecision.from_validation(
                validation,
                decision_id=f"skill.selection.{index}",
                eligible=eligible,
                reason_code="skill.context_intent_match" if eligible else "skill.context_intent_mismatch",
                intent_tags=(intent_value,),
                manifest=manifest,
            )
        )
    return tuple(decisions)
