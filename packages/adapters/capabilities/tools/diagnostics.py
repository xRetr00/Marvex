"""Capability diagnostics tool — read-only count of registered capabilities."""

from __future__ import annotations

from typing import Callable, ClassVar

from pydantic import BaseModel, ConfigDict

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result


class CapabilityDiagnosticsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityDiagnosticsTool(Tool):
    id: ClassVar[str] = "capability_diagnostics"
    name: ClassVar[str] = "Capability Diagnostics"
    description: ClassVar[str] = "Report how many capabilities are registered and eligible."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = CapabilityDiagnosticsParams

    def __init__(self, *, count_provider: Callable[[], int] | None = None) -> None:
        # Defaults to a static count; the registry injects a live counter so the
        # number reflects the actual registered tool set.
        self._count_provider = count_provider or (lambda: 0)

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        count = max(0, int(self._count_provider()))
        return succeeded_result(
            request,
            {"capability_count": count, "eligible_count": count},
        )


__all__ = ["CapabilityDiagnosticsTool", "CapabilityDiagnosticsParams"]
