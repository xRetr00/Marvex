"""Intent validator port signatures only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.intent_models import IntentDecision
from packages.contracts.intent_validation_models import IntentValidationResult


@runtime_checkable
class IntentValidatorPort(Protocol):
    """Signature-only intent validation boundary."""

    def validate(self, input_text: str, intent_decision: IntentDecision) -> IntentValidationResult:
        ...
