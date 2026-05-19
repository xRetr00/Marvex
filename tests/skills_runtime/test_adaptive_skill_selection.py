from __future__ import annotations

from packages.skills_runtime import SkillManifest, SkillPromptContribution, SkillRef, SkillResourceKind, SkillResourceRef
from packages.skills_runtime.selection import select_skills_for_intent
from packages.intent_runtime import IntentKind


def _manifest(skill_id: str, when_to_use: str) -> SkillManifest:
    ref = SkillRef(skill_id=skill_id)
    return SkillManifest(
        schema_version="1",
        skill_ref=ref,
        display_name=skill_id,
        description=f"Skill for {skill_id}",
        instruction_ref=SkillResourceRef(kind=SkillResourceKind.INSTRUCTION, uri=f"local://skills/{skill_id}/SKILL.md"),
        prompt_contributions=(SkillPromptContribution(schema_version="1", contribution_id=f"{skill_id}.contrib", skill_ref=ref, summary=f"Use {skill_id} safely", when_to_use=when_to_use, max_context_chars=300),),
    )


def test_skill_selection_uses_intent_and_context_without_static_all_skill_dump() -> None:
    web_skill = _manifest("web-research", "Use for grounded web search and citation evidence")
    browser_skill = _manifest("browser-agent", "Use for browser navigation only")

    decisions = select_skills_for_intent(intent_kind=IntentKind.GROUNDED_ANSWER, context_terms=("citation", "evidence"), manifests=(web_skill, browser_skill))

    assert [decision.validation.skill_ref.skill_id for decision in decisions if decision.eligible] == ["web-research"]
    assert decisions[0].prompt_contributions_delivered
    assert decisions[1].eligible is False
