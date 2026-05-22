from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.cognition_runtime import CognitionRuntime
from packages.intent_runtime import IntentKind, classification_from_kind
from packages.skills_runtime import DeterministicFakeSkillPackage, SkillInstructionLoader


def _turn_input(text: str) -> Any:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-skill-loader-cognition",
        event_id="turn-skill-loader-cognition:input",
        text=text,
        timestamp=datetime.now(UTC),
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-skill-loader-cognition",
        turn_id="turn-skill-loader-cognition",
        input_event=event,
    )


def test_cognition_injects_loaded_skill_prompt_contribution_for_skill_route(tmp_path) -> None:
    skill_dir = tmp_path / "summary"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# Summary Skill\nUse concise neutral bullets for summaries.",
        encoding="utf-8",
    )
    package = DeterministicFakeSkillPackage.summary_skill()

    runtime = CognitionRuntime(
        intent_classifier=lambda request: classification_from_kind(
            request,
            kind=IntentKind.SKILL_NEEDED,
            score=0.91,
            reason_code="test.skill",
        ),
        skill_manifests=(package.manifest,),
        skill_loader=SkillInstructionLoader(local_skill_root=tmp_path),
    )

    result = runtime.assemble_turn(_turn_input("Use the summary skill."))

    included = result.context_projection.included_sources
    assert {"kind": "skill_prompt_contribution", "identifier": "skill.summary.summary-context.loaded"} in included
    assert "skill_contribution" in result.prompt_projection.section_kinds
    assert all(candidate.raw_content_persisted is False for candidate in result.context_pack.included)
    serialized = result.model_dump_json().lower()
    assert "ignore previous instructions" not in serialized
