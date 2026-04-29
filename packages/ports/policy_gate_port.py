"""Policy gate port signatures only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.intent_models import IntentDecision, PolicyDecision


@runtime_checkable
class PolicyGatePort(Protocol):
    """Signature-only policy decision boundary."""

    def decide(self, intent_decision: IntentDecision) -> PolicyDecision:
        ...
