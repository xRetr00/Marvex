from packages.intent_runtime.models import (
    ClarificationNeededDecision,
    IntentAmbiguitySignal,
    IntentCandidate,
    IntentClassificationRequest,
    IntentClassificationResult,
    IntentConfidence,
    IntentConfidenceBucket,
    IntentKind,
    IntentRef,
    IntentRiskSignal,
    IntentRouteDecision,
    SafeIntentProjection,
    classification_from_kind,
    classify_intent,
)

_HYBRID_EXPORTS = {
    "CapabilityAvailability",
    "HybridIntentRuntime",
    "IntentPlan",
    "IntentStep",
}

__all__ = [
    "ClarificationNeededDecision",
    "IntentAmbiguitySignal",
    "IntentCandidate",
    "IntentClassificationRequest",
    "IntentClassificationResult",
    "IntentConfidence",
    "IntentConfidenceBucket",
    "IntentKind",
    "IntentRef",
    "IntentRiskSignal",
    "IntentRouteDecision",
    "SafeIntentProjection",
    "classification_from_kind",
    "classify_intent",
    "CapabilityAvailability",
    "HybridIntentRuntime",
    "IntentPlan",
    "IntentStep",
]


def __getattr__(name: str):
    if name in _HYBRID_EXPORTS:
        from . import hybrid

        value = getattr(hybrid, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
