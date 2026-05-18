import pytest

from packages.context_runtime import ContextBudget, ContextCandidate, ContextPack, ContextSourceKind, ContextSourceRef
from packages.intent_runtime import IntentKind, IntentRef
from packages.prompt_harness_runtime import (
    CompactionCandidate,
    ContextOverflowStrategy,
    HarnessValidationResult,
    PlanningNeedDecision,
    PromptAssemblyRequest,
    PromptSectionKind,
    ToolResultClearingDecision,
    assemble_prompt_harness,
    decide_compaction,
)


def _pack() -> ContextPack:
    candidate = ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier="input.1"), "Need a calculator", token_estimate=5, intent_tags=("capability_tool",))
    return ContextPack(schema_version="1", trace_id="trace-1", turn_id="turn-1", intent_ref=IntentRef(intent_id="intent.tool", intent_kind=IntentKind.CAPABILITY_TOOL), budget=ContextBudget(max_context_tokens=60, reserved_response_tokens=20), included=(candidate,), excluded=(), used_context_tokens=5)


def test_prompt_harness_assembles_bounded_safe_sections_without_raw_prompt_dump() -> None:
    result = assemble_prompt_harness(PromptAssemblyRequest(schema_version="1", trace_id="trace-1", turn_id="turn-1", intent_ref=IntentRef(intent_id="intent.tool", intent_kind=IntentKind.CAPABILITY_TOOL), context_pack=_pack()))

    kinds = [section.kind for section in result.plan.sections]
    assert PromptSectionKind.SYSTEM_POLICY in kinds
    assert PromptSectionKind.USER_CONTEXT in kinds
    assert result.budget_report.within_budget is True
    assert result.safe_projection().raw_prompt_persisted is False
    assert "Need a calculator" not in result.safe_projection().model_dump_json()


def test_prompt_harness_rejects_raw_sections_and_overbudget_sections() -> None:
    candidate = CompactionCandidate(source_ref=ContextSourceRef(kind=ContextSourceKind.TOOL_RESULT, identifier="tool.result.1"), token_estimate=300, retention_reason="tool_result_old", safe_summary="large result")
    decision = decide_compaction(candidate, max_tokens=100)

    assert decision.strategy == ContextOverflowStrategy.OFFLOAD_BY_REF
    assert decision.safe_projection().raw_content_persisted is False
    assert ToolResultClearingDecision.from_candidate(candidate).clear_from_prompt is True


def test_planning_and_validation_summaries_are_safe() -> None:
    planning = PlanningNeedDecision.from_intent(IntentRef(intent_id="intent.tool", intent_kind=IntentKind.CAPABILITY_TOOL), context_candidate_count=3)
    validation = HarnessValidationResult.validated(schema_version="1", trace_id="trace-1", turn_id="turn-1", prompt_section_count=4)

    assert planning.planning_needed is True
    assert planning.autonomous_loop_started is False
    assert validation.valid is True
    assert validation.raw_prompt_persisted is False


def test_prompt_harness_result_requires_safe_projection_input() -> None:
    pack = _pack().model_copy(update={"all_context_injected": True})
    with pytest.raises(ValueError, match="all-context injection"):
        assemble_prompt_harness(PromptAssemblyRequest(schema_version="1", trace_id="trace-1", turn_id="turn-1", intent_ref=IntentRef(intent_id="intent.tool", intent_kind=IntentKind.CAPABILITY_TOOL), context_pack=pack))
