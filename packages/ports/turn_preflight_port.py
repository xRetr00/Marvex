"""Turn preflight port signatures only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.turn_preflight_models import TurnPreflightResult


@runtime_checkable
class TurnPreflightPort(Protocol):
    """Signature-only turn preflight boundary."""

    def run(self, input_text: str, enabled: bool) -> TurnPreflightResult:
        ...
