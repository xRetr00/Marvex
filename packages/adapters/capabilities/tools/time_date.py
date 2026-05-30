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
    # Default to the machine's local timezone (the user's wall clock on a
    # local-first desktop), not UTC. "UTC" stays available for callers that
    # explicitly want it.
    timezone: Literal["local", "UTC"] = "local"


class TimeDateTool(Tool):
    id: ClassVar[str] = "time_date"
    name: ClassVar[str] = "Time and Date"
    description: ClassVar[str] = "Return the current local date and time (with timezone)."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = TimeDateParams

    def __init__(self, *, clock: Callable[[], dt.datetime] | None = None) -> None:
        # The clock must return a timezone-aware datetime; default is the local
        # machine time WITH its real offset (astimezone() with no arg).
        self._clock = clock or (lambda: dt.datetime.now().astimezone())

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = TimeDateParams(**request.arguments)
        moment = self._clock()
        if moment.tzinfo is None:
            moment = moment.astimezone()
        now = moment.astimezone(dt.timezone.utc) if params.timezone == "UTC" else moment.astimezone()
        label = _tz_label(now)
        display = f"{now.strftime('%A, %B %d, %Y at %H:%M')} ({label})"
        return succeeded_result(
            request,
            {
                "timezone": label,
                "utc_offset": now.strftime("%z"),
                "iso_datetime": now.isoformat(),
                "iso_date": now.date().isoformat(),
                "display": display,
            },
        )


def _tz_label(moment: dt.datetime) -> str:
    name = moment.tzname() or ""
    offset = moment.strftime("%z")
    pretty_offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"
    if name and name.upper() != "UTC" and not name.startswith("UTC"):
        return f"{name}, {pretty_offset}"
    return name or pretty_offset


__all__ = ["TimeDateTool", "TimeDateParams"]
