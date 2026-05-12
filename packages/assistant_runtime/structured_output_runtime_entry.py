from __future__ import annotations

from typing import Any

from .structured_output_consumer import (
    AssistantStructuredOutputConsumptionDraft,
    AssistantStructuredOutputInputDraft,
    consume_structured_output_handoff_draft,
)


def consume_structured_output_for_future_stage(
    handoff_input: AssistantStructuredOutputInputDraft | dict[str, Any],
) -> AssistantStructuredOutputConsumptionDraft:
    draft = (
        handoff_input
        if isinstance(handoff_input, AssistantStructuredOutputInputDraft)
        else AssistantStructuredOutputInputDraft(
            **_normalize_handoff_like_dict(handoff_input)
        )
    )
    return consume_structured_output_handoff_draft(draft)


def _normalize_handoff_like_dict(value: dict[str, Any]) -> dict[str, Any]:
    data = dict(value)
    if "source_state" not in data and "state" in data:
        data["source_state"] = data.pop("state")
    return data
