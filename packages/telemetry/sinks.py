from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from packages.contracts import TraceEvent, TraceLevel, TraceStage
from packages.telemetry.sanitization import sanitize_trace_data


STRUCTURED_OUTPUT_TRACE_KEYS = frozenset(
    {
        "consumptionstatus",
        "diagnosticonly",
        "handoffstatus",
        "sanitizederrorcode",
        "sanitizedmessage",
        "sourcestate",
        "structuredoutput",
        "targetcontract",
        "state",
        "rawoutput",
        "rawprovideroutput",
        "rawresponse",
        "rawmetadata",
        "rawpreview",
        "parsedpayload",
        "prompt",
        "fullprompt",
        "systemprompt",
        "messages",
        "conversation",
        "transcript",
        "providerresponseid",
        "previousresponseid",
        "responseid",
        "sessionid",
        "conversationid",
        "threadid",
        "apikey",
        "authorization",
        "bearer",
        "token",
        "secret",
        "password",
    }
)


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
    safe_data = _safe_trace_data(data)
    return TraceEvent(
        schema_version=schema_version,
        trace_id=trace_id,
        event_id=f"{turn_id}:{stage.value}",
        timestamp=timestamp or datetime.now(UTC),
        stage=stage,
        level=level,
        message=message,
        data=safe_data,
    )


def _safe_trace_data(data: dict[str, object] | None) -> dict[str, object]:
    copied = dict(data or {})
    if _looks_like_structured_output_trace_data(copied):
        return dict(sanitize_trace_data(copied))
    return copied


def _looks_like_structured_output_trace_data(data: dict[str, object]) -> bool:
    normalized_keys = {_normalize_trace_key(key) for key in data}
    return bool(normalized_keys.intersection(STRUCTURED_OUTPUT_TRACE_KEYS))


def _normalize_trace_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())
