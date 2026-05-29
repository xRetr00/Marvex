"""Time/date tool — safe current UTC time/date projection."""

from __future__ import annotations

import datetime as dt
from typing import Callable, ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result


class TimeDateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timezone: Literal["UTC"] = "UTC"


class TimeDateTool(Tool):
    id: ClassVar[str] = "time_date"
    name: ClassVar[str] = "Time and Date"
    description: ClassVar[str] = "Return the current UTC date and time."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = TimeDateParams

    def __init__(self, *, clock: Callable[[], dt.datetime] | None = None) -> None:
        self._clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = TimeDateParams(**request.arguments)
        now = self._clock().astimezone(dt.timezone.utc)
        return succeeded_result(
            request,
            {
                "timezone": params.timezone,
                "iso_datetime": now.isoformat(),
                "iso_date": now.date().isoformat(),
            },
        )


__all__ = ["TimeDateTool", "TimeDateParams"]
