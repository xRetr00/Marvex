"""Intent router port signatures only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.intent_models import IntentDecision


@runtime_checkable
class IntentRouterPort(Protocol):
    """Signature-only intent route-family boundary."""

    def decide_route(self, input_text: str) -> IntentDecision:
        ...
