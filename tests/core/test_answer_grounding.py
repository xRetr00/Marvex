"""Tests for grounded-answer self-correction (docs/TODO/05).

Clarification is now model-driven via the clarify tool (see
tests/core/test_clarify_tool_loop.py), not a backend keyword match.
"""

from packages.core.orchestration.answer_grounding import (
    assess_grounded_answer,
    build_correction_prompt,
)


def test_currency_claim_without_evidence_needs_correction():
    assessment = assess_grounded_answer("The latest model is GPT-4o, released 2026.", evidence_count=0)
    assert assessment.needs_correction
    assert assessment.reason_code == "answer.currency_claim_without_evidence"


def test_currency_claim_with_evidence_but_no_citation_needs_correction():
    assessment = assess_grounded_answer("GPT-4o is currently the newest model.", evidence_count=3)
    assert assessment.needs_correction
    assert assessment.reason_code == "answer.currency_claim_uncited"


def test_currency_claim_with_citation_is_ok():
    assessment = assess_grounded_answer(
        "The latest model is X [web.evidence.1].", evidence_count=2
    )
    assert not assessment.needs_correction
    assert assessment.status == "ok"


def test_non_currency_answer_is_ok_without_citation():
    assessment = assess_grounded_answer("Paris is the capital of France.", evidence_count=0)
    assert not assessment.needs_correction


def test_empty_answer_needs_correction():
    assessment = assess_grounded_answer("   ", evidence_count=5)
    assert assessment.needs_correction
    assert assessment.reason_code == "answer.empty"


def test_correction_prompt_includes_reason_and_original():
    prompt = build_correction_prompt(
        original_user_input="latest model by openai",
        previous_answer="GPT-4o, released 2026.",
        reason_code="answer.currency_claim_without_evidence",
    )
    assert "latest model by openai" in prompt
    assert "GPT-4o, released 2026." in prompt
    assert "no web evidence" in prompt.lower()
    assert "cannot verify" in prompt.lower()
