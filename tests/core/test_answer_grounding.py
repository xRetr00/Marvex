"""Tests for grounded-answer clarification + self-correction (docs/TODO/05)."""

from packages.core.orchestration.answer_grounding import (
    assess_grounded_answer,
    build_correction_prompt,
    detect_ambiguous_subject,
)


def test_open_ai_spaced_is_ambiguous_and_asks_company_vs_open_weight():
    question = detect_ambiguous_subject("what is the latest model by open ai")
    assert question is not None
    assert "OpenAI" in question.title
    ids = {option.id for option in question.options}
    assert {"openai_company", "open_weight"} <= ids
    # The prompt text the assistant would speak/show lists the options.
    text = question.prompt_text()
    assert "A)" in text and "B)" in text


def test_openai_no_space_is_not_ambiguous():
    assert detect_ambiguous_subject("what is the latest model by openai") is None


def test_collapses_extra_spaces_in_trigger():
    assert detect_ambiguous_subject("the open   ai company") is not None


def test_unrelated_text_is_not_ambiguous():
    assert detect_ambiguous_subject("what time is it") is None
    assert detect_ambiguous_subject("read my report.pdf") is None


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
