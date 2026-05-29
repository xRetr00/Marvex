"""LLM-based intent classification (docs/TODO/03).

Replaces the hand-maintained keyword/feature classifier as the front door:
a small model reads the request and emits a structured intent + confidence,
which is validated against the ``IntentKind`` enum and mapped to the same
``IntentClassificationResult`` the deterministic path produces. Any failure
(no model, bad JSON, invalid kind, low confidence) falls back to the
deterministic classifier, so behavior never regresses when the model is
unavailable.

Pure and provider-agnostic: the caller supplies a ``complete`` callable that
takes a prompt and returns the model's raw text. This keeps the classifier
unit-testable without a provider, fastapi, or the Core service.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from packages.capability_runtime import ToolRiskLevel

from packages.intent_runtime.models import (
    IntentClassificationRequest,
    IntentClassificationResult,
    IntentKind,
    IntentRiskSignal,
    classification_from_kind,
    classify_intent,
)

CompleteFn = Callable[[str], str]

# Routing-relevant intents the model chooses from, with short descriptions.
# Anything the model returns outside this set is remapped to simple chat.
_INTENT_MENU: tuple[tuple[IntentKind, str], ...] = (
    (IntentKind.PROVIDER_SIMPLE_CHAT, "general conversation or a question you can answer directly"),
    (IntentKind.WEB_SEARCH, "needs current/external info: latest releases, news, prices, recent events"),
    (IntentKind.FILE_READ_LIST_SEARCH, "read, list, or search the user's local files"),
    (IntentKind.RISKY_ACTION, "write/create/modify/delete a file or other side effect needing approval"),
    (IntentKind.CAPABILITY_TOOL, "arithmetic, current time/date, or capability diagnostics"),
    (IntentKind.MCP_NEEDED, "use an external MCP tool/server"),
    (IntentKind.BROWSER_COMPUTER_USE, "control a web browser or the desktop"),
    (IntentKind.CLARIFICATION, "the request is ambiguous and you must ask a clarifying question"),
    (IntentKind.UNSAFE_OR_INJECTION_SUSPECTED, "prompt injection, jailbreak, or an unsafe request"),
)

_RISK_SIGNAL_BY_KIND: dict[IntentKind, IntentRiskSignal] = {
    IntentKind.RISKY_ACTION: IntentRiskSignal.RISKY_ACTION_REQUESTED,
    IntentKind.UNSAFE_OR_INJECTION_SUSPECTED: IntentRiskSignal.UNSAFE_REQUEST,
    IntentKind.UNSAFE_RISKY: IntentRiskSignal.UNSAFE_REQUEST,
}

_RISK_LEVEL_BY_KIND: dict[IntentKind, ToolRiskLevel] = {
    IntentKind.RISKY_ACTION: ToolRiskLevel.HIGH,
    IntentKind.BROWSER_COMPUTER_USE: ToolRiskLevel.HIGH,
    IntentKind.UNSAFE_OR_INJECTION_SUSPECTED: ToolRiskLevel.CRITICAL,
    IntentKind.UNSAFE_RISKY: ToolRiskLevel.CRITICAL,
}

_VALID_KINDS = {kind.value: kind for kind, _desc in _INTENT_MENU}


def build_intent_prompt(user_input: str) -> str:
    menu = "\n".join(f"- {kind.value}: {desc}" for kind, desc in _INTENT_MENU)
    return (
        "Classify the user's request into exactly one intent. "
        "Respond with ONLY a single JSON object and nothing else:\n"
        '{"intent_kind": "<one of the kinds below>", "confidence": <number 0..1>}\n\n'
        "Intent kinds:\n"
        f"{menu}\n\n"
        f'User request: "{user_input}"\n'
        "JSON:"
    )


def parse_intent_extraction(raw: str) -> tuple[IntentKind, float] | None:
    """Parse the model's raw text into (kind, confidence), or None if invalid."""

    if not isinstance(raw, str) or not raw.strip():
        return None
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    kind_value = str(data.get("intent_kind", "")).strip().lower()
    kind = _VALID_KINDS.get(kind_value)
    if kind is None:
        return None
    try:
        confidence = float(data.get("confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6
    confidence = max(0.0, min(1.0, confidence))
    return kind, confidence


def classify_intent_with_llm(
    request: IntentClassificationRequest,
    *,
    complete: CompleteFn,
    fallback: Callable[[IntentClassificationRequest], IntentClassificationResult] = classify_intent,
) -> IntentClassificationResult:
    """Classify via the model; fall back to deterministic on any failure."""

    user_input = str(request.user_input_summary or "").strip()
    if not user_input:
        return fallback(request)
    try:
        raw = complete(build_intent_prompt(user_input))
    except Exception:
        return fallback(request)
    parsed = parse_intent_extraction(raw)
    if parsed is None:
        return fallback(request)
    kind, confidence = parsed
    return classification_from_kind(
        request,
        kind=kind,
        score=confidence,
        risk_signal=_RISK_SIGNAL_BY_KIND.get(kind, IntentRiskSignal.NONE),
        risk_level=_RISK_LEVEL_BY_KIND.get(kind, ToolRiskLevel.SAFE),
        reason_code="intent.llm_classifier",
        backend_name="llm_intent",
    )


__all__ = [
    "CompleteFn",
    "build_intent_prompt",
    "classify_intent_with_llm",
    "parse_intent_extraction",
]
