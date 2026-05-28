"""Pure helpers for the default-route agentic provider loop.

Lives outside of ``services.core.main`` so it can be unit-tested without
booting the full Core service (which pulls FastAPI, the full provider
worker chain, and platform-specific dependencies).

These helpers replace the previous one-shot ``run_provider_stage`` ->
``finalize`` sequence with a bounded continuation loop. The loop is
conservative on purpose:

* It does **not** dispatch tool calls. Tool/grounded/MCP/file/etc. routes
  retain their own dedicated handlers higher up the dispatcher.
* It only continues when the provider response was truncated by token
  budget (``finish_reason == "length"``).
* It caps total iterations at the planner's recommended ``max_steps``
  value, further bounded by ``MARVEX_AGENTIC_MAX_STEPS`` and a hard
  module ceiling so a misconfigured model can't spin forever.
"""

from __future__ import annotations

import os
from typing import Any

from packages.contracts import AssistantTurnInput, AssistantTurnResult


AGENTIC_MAX_STEPS_ENV = "MARVEX_AGENTIC_MAX_STEPS"
AGENTIC_LOOP_HARD_CEILING = 6


def resolve_agentic_max_steps(planner_max_steps: int) -> int:
    """Resolve the agentic loop iteration cap.

    Honours the planner's recommendation but lets operators tighten or
    relax it via env override. Hard ceiling avoids runaway loops on
    misconfigured models.
    """

    planner = max(1, int(planner_max_steps or 1))
    override = os.environ.get(AGENTIC_MAX_STEPS_ENV, "").strip()
    if override.isdigit():
        try:
            requested = int(override)
        except ValueError:
            requested = planner
        return max(1, min(requested, AGENTIC_LOOP_HARD_CEILING))
    return max(1, min(planner, AGENTIC_LOOP_HARD_CEILING))


def provider_response_id(result: AssistantTurnResult | None) -> str | None:
    """Return the first non-empty provider response id on the turn, if any."""

    if result is None:
        return None
    for ref in getattr(result, "provider_turn_refs", ()) or ():
        ref_id = getattr(ref, "ref_id", None)
        if isinstance(ref_id, str) and ref_id.strip():
            return ref_id.strip()
    metadata = getattr(result, "metadata", {}) or {}
    if isinstance(metadata, dict):
        candidate = metadata.get("provider_response_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def provider_truncated(result: AssistantTurnResult | None) -> bool:
    """Detect whether the provider response was cut off by a token budget."""

    if result is None or getattr(result, "error", None) is not None:
        return False
    final = getattr(result, "assistant_final_response", None)
    finish = getattr(final, "finish_reason", None)
    finish_value = getattr(finish, "value", finish)
    if isinstance(finish_value, str) and finish_value.strip().lower() == "length":
        return True
    metadata = getattr(result, "metadata", {}) or {}
    if isinstance(metadata, dict):
        candidate = metadata.get("provider_finish_reason")
        if isinstance(candidate, str) and candidate.strip().lower() == "length":
            return True
        provider = metadata.get("provider")
        if isinstance(provider, dict):
            candidate = provider.get("finish_reason")
            if isinstance(candidate, str) and candidate.strip().lower() == "length":
                return True
    return False


def should_continue_provider_loop(
    result: AssistantTurnResult | None,
    step_index: int,
    max_steps: int,
) -> bool:
    """Decide whether the default provider route should iterate again."""

    if step_index + 1 >= max_steps:
        return False
    if result is None:
        return False
    if getattr(result, "error", None) is not None:
        return False
    if not provider_truncated(result):
        return False
    return True


def continuation_turn_input(
    provider_turn_input: AssistantTurnInput, step_index: int
) -> AssistantTurnInput:
    """Return a follow-up turn input asking the model to continue."""

    continuation_text = (
        f"Continue the previous response from where it was cut off. "
        f"This is continuation step {step_index + 2}."
    )
    return provider_turn_input.model_copy(
        update={"user_visible_input": continuation_text}
    )


__all__ = [
    "AGENTIC_LOOP_HARD_CEILING",
    "AGENTIC_MAX_STEPS_ENV",
    "continuation_turn_input",
    "provider_response_id",
    "provider_truncated",
    "resolve_agentic_max_steps",
    "should_continue_provider_loop",
]
