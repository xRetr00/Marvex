from __future__ import annotations

from packages.learning_runtime import (
    AnswerRating,
    FeedbackEvent,
    FeedbackSignalKind,
    IntentFailureFeedback,
    LearningLoop,
    MemoryUseFeedback,
    ToolOutcomeFeedback,
    UserCorrection,
)


def test_user_correction_creates_review_required_memory_skill_and_policy_candidates() -> None:
    event = FeedbackEvent.from_user_correction(
        trace_id="trace-learn",
        turn_id="turn-learn",
        correction=UserCorrection(text="I prefer recent Marvex source evidence before tool suggestions", applies_to="answer"),
    )

    summary = LearningLoop.default().process((event,))

    assert summary.memory_write_candidates
    assert summary.skill_improvement_candidates
    assert summary.preference_candidates
    assert all(candidate.review_required for candidate in summary.memory_write_candidates)
    assert summary.safe_projection().raw_feedback_persisted is False


def test_tool_memory_and_intent_feedback_update_safe_learning_candidates_without_silent_mutation() -> None:
    events = (
        FeedbackEvent(trace_id="trace-tool", turn_id="turn-tool", signal_kind=FeedbackSignalKind.TOOL_OUTCOME, payload=ToolOutcomeFeedback(tool_ref="tool.calculator", succeeded=True, outcome_reason="useful arithmetic result")),
        FeedbackEvent(trace_id="trace-memory", turn_id="turn-memory", signal_kind=FeedbackSignalKind.MEMORY_USE, payload=MemoryUseFeedback(memory_ref="memory.chunk.1", useful=True, reason="selected evidence was relevant")),
        FeedbackEvent(trace_id="trace-intent", turn_id="turn-intent", signal_kind=FeedbackSignalKind.INTENT_FAILURE, payload=IntentFailureFeedback(input_summary="latest dependency docs", expected_intent="web_search", actual_intent="simple_chat")),
        FeedbackEvent(trace_id="trace-rating", turn_id="turn-rating", signal_kind=FeedbackSignalKind.ANSWER_RATING, payload=AnswerRating(rating=2, reason="missing citations")),
    )

    summary = LearningLoop.default().process(events)

    assert summary.skill_improvement_candidates
    assert summary.policy_tuning_candidates
    assert summary.memory_hotness_updates[0].memory_ref == "memory.chunk.1"
    assert summary.route_example_candidates[0].expected_intent == "web_search"
    assert summary.silent_policy_mutation is False
    assert summary.silent_skill_mutation is False
