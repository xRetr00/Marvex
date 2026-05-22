from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.skills_runtime import DeterministicFakeSkillPackage, SkillInstructionLoader
from packages.telemetry import InMemoryTraceReader
from services.core.main import _CoreServiceProviderWorkerTurnExecutor


class _SkillIntentClassifier:
    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": "intent.skill_needed",
                    "intent_kind": "skill_needed",
                },
                "confidence_bucket": "high",
                "risk_signal": "none",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


def _turn_input(text: str) -> Any:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-skill-loader",
        event_id="turn-core-skill-loader:input",
        text=text,
        timestamp=datetime.now(UTC),
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-skill-loader",
        turn_id="turn-core-skill-loader",
        input_event=event,
    )


def test_core_skill_route_reports_loaded_local_skill_contribution(tmp_path) -> None:
    skill_dir = tmp_path / "summary"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# Summary Skill\nUse concise neutral bullets for summaries.",
        encoding="utf-8",
    )
    package = DeterministicFakeSkillPackage.summary_skill()
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        skill_manifests=(package.manifest,),
        skill_loader=SkillInstructionLoader(local_skill_root=tmp_path),
    )
    executor._intent_classifier = _SkillIntentClassifier()

    result = executor.submit_turn(_turn_input("Use the summary skill."))

    assert result.error is None
    assert result.metadata["skill"]["local_skill_loader_available"] is True
    assert result.metadata["skill"]["loaded_skill_contribution_count"] == 1
    assert result.metadata["skill"]["script_execution_allowed"] is False
    assert result.metadata["skill"]["remote_loading_allowed"] is False
