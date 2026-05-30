"""Grounded-answer clarification + self-correction (docs/TODO/05).

Two jobs the grounded-answer path was missing, both visible in the field logs:

1. **Clarify ambiguous subjects.** A user who types "open ai" (with a space)
   may mean OpenAI (the company) or open-source / open-weight AI models. The
   assistant answered confidently for the wrong reading instead of asking. This
   module detects a small, data-driven set of ambiguous subjects and returns a
   structured clarification question (consumable by the UI QuestionTool).

2. **Verify before answering "latest/current".** A local model happily said
   "GPT-4o is OpenAI's latest model (released 2026)" - a stale training-data
   fact stated as current. When an answer asserts a current/latest claim that
   the gathered evidence does not support, we don't block and we don't answer
   for the model: we mark the answer unsupported and re-prompt the SAME model to
   correct itself in the same turn (once), then fall back to an honest "could not
   verify" instead of fabricating.

Pure functions only - no fastapi / provider imports - so this is unit-testable
without booting the Core service.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ClarificationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = ""


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = "single"
    title: str = Field(..., min_length=1)
    options: tuple[ClarificationOption, ...] = ()
    allow_custom: bool = True

    def prompt_text(self) -> str:
        lines = [self.title]
        for index, option in enumerate(self.options):
            letter = chr(ord("A") + index)
            suffix = f" - {option.description}" if option.description else ""
            lines.append(f"{letter}) {option.label}{suffix}")
        return "\n".join(lines)

    def safe_projection(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "title": self.title,
            "allow_custom": self.allow_custom,
            "options": [
                {"id": option.id, "label": option.label, "description": option.description}
                for option in self.options
            ],
        }


# Data-driven ambiguous-subject table. Each entry: the lowercased trigger phrase
# that must appear as a standalone token sequence, plus the disambiguation
# question. Extend this rather than adding bespoke if-branches.
_AMBIGUOUS_SUBJECTS: tuple[tuple[str, ClarificationQuestion], ...] = (
    (
        "open ai",
        ClarificationQuestion(
            title="Did you mean OpenAI (the company) or open / open-weight AI models?",
            options=(
                ClarificationOption(id="openai_company", label="OpenAI (the company)", description="e.g. ChatGPT, GPT models"),
                ClarificationOption(id="open_weight", label="Open / open-weight AI models", description="open-source models you can download"),
            ),
        ),
    ),
)


def detect_ambiguous_subject(text: str | None) -> ClarificationQuestion | None:
    """Return a clarification question if the input has an ambiguous subject.

    The trigger must appear with word boundaries so "openai" (no space) does
    NOT match the "open ai" trigger - the whole point is that the spaced form is
    the ambiguous one.
    """

    lowered = f" {(text or '').lower().strip()} "
    # Collapse internal whitespace so "open   ai" still triggers.
    lowered = " ".join(lowered.split())
    lowered = f" {lowered} "
    for trigger, question in _AMBIGUOUS_SUBJECTS:
        needle = f" {trigger} "
        if needle in lowered:
            return question
    return None


class AnswerAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str  # "ok" | "needs_correction"
    reason_code: str = ""

    @property
    def needs_correction(self) -> bool:
        return self.status == "needs_correction"


_CURRENCY_CLAIM_MARKERS: tuple[str, ...] = (
    "latest",
    "newest",
    "most recent",
    "currently",
    "current ",
    "as of now",
    "right now",
    "today",
    "this year",
)


def _claims_currency(answer_text: str) -> bool:
    lowered = answer_text.lower()
    return any(marker in lowered for marker in _CURRENCY_CLAIM_MARKERS)


def _has_citation(answer_text: str) -> bool:
    # Grounded citations look like [web.evidence.1] / [memory.evidence.x].
    lowered = answer_text.lower()
    return "[web.evidence" in lowered or "[memory.evidence" in lowered


def assess_grounded_answer(
    answer_text: str | None,
    *,
    evidence_count: int,
    now: dt.datetime | None = None,
) -> AnswerAssessment:
    """Decide whether a grounded answer is trustworthy or needs self-correction.

    Flags ``needs_correction`` when the answer makes a current/latest claim but
    either (a) no evidence was gathered, or (b) the answer cites no evidence ref
    - i.e. it is answering a time-sensitive question from memory, which is
    exactly how stale facts ("GPT-4o is the latest, released 2026") slip through.
    """

    del now  # reserved for future date-contradiction checks
    text = (answer_text or "").strip()
    if not text:
        return AnswerAssessment(status="needs_correction", reason_code="answer.empty")
    if _claims_currency(text):
        if evidence_count <= 0:
            return AnswerAssessment(status="needs_correction", reason_code="answer.currency_claim_without_evidence")
        if not _has_citation(text):
            return AnswerAssessment(status="needs_correction", reason_code="answer.currency_claim_uncited")
    return AnswerAssessment(status="ok", reason_code="answer.supported")


def build_correction_prompt(*, original_user_input: str, previous_answer: str, reason_code: str) -> str:
    """Re-prompt the SAME model to correct an unsupported answer in-turn."""

    why = {
        "answer.empty": "Your previous answer was empty.",
        "answer.currency_claim_without_evidence": (
            "Your previous answer stated a current/latest fact, but no web evidence was available to support it."
        ),
        "answer.currency_claim_uncited": (
            "Your previous answer stated a current/latest fact without citing any web evidence ref."
        ),
    }.get(reason_code, "Your previous answer could not be verified against the available evidence.")
    return (
        f"{why}\n\n"
        f'Original question: "{original_user_input.strip()}"\n'
        f'Your previous answer: "{previous_answer.strip()}"\n\n'
        "Correct it now. Only state a current/latest fact if a provided web.evidence ref supports it, and "
        "cite that ref inline like [web.evidence.1]. If the evidence does not establish the current answer, "
        "say plainly that you cannot verify it from the available evidence and do NOT answer from memory. "
        "Never present training-data facts as current."
    )


__all__ = [
    "ClarificationOption",
    "ClarificationQuestion",
    "detect_ambiguous_subject",
    "AnswerAssessment",
    "assess_grounded_answer",
    "build_correction_prompt",
]
