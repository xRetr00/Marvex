"""Decision pipeline port signatures only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts.decision_pipeline_models import DecisionPipelineResult


@runtime_checkable
class DecisionPipelinePort(Protocol):
    """Signature-only decision pipeline boundary."""

    def run(self, input_text: str) -> DecisionPipelineResult:
        ...
