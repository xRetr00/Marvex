from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from packages.contracts import TraceEvent, TraceLevel, TraceStage


@runtime_checkable
class TelemetrySink(Protocol):
    def emit(self, event: TraceEvent) -> None:
        ...


class NoopTelemetrySink:
    def emit(self, event: TraceEvent) -> None:
        return None


def make_trace_event(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    stage: TraceStage,
    level: TraceLevel,
    message: str,
    data: dict[str, object] | None = None,
    timestamp: datetime | None = None,
) -> TraceEvent:
    return TraceEvent(
        schema_version=schema_version,
        trace_id=trace_id,
        event_id=f"{turn_id}:{stage.value}",
        timestamp=timestamp or datetime.now(UTC),
        stage=stage,
        level=level,
        message=message,
        data=dict(data or {}),
    )
