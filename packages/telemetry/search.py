from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class TraceReadable(Protocol):
    def read_trace(self, trace_id: str) -> dict[str, Any] | None: ...


class TelemetrySearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TraceSearchQuery(TelemetrySearchModel):
    schema_version: str = Field(..., min_length=1)
    session_ref_id: str | None = None
    conversation_ref_id: str | None = None
    tool_status: str | None = None
    approval_status: str | None = None
    status: str | None = None
    max_results: int = Field(default=25, ge=1, le=100)

    @field_validator("session_ref_id", "conversation_ref_id", "tool_status", "approval_status", "status")
    @classmethod
    def _validate_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip() or value != value.strip():
            raise ValueError("trace search filters must be non-empty and trimmed")
        if any(character not in _SAFE_ID_CHARS for character in value):
            raise ValueError("trace search filters must contain only safe id characters")
        return value


class TraceSearchSummary(TelemetrySearchModel):
    trace_id: str
    event_count: int = Field(..., ge=0)
    session_ref_id: str | None = None
    conversation_ref_id: str | None = None
    status: str | None = None
    tool_status: str | None = None
    approval_status: str | None = None
    raw_payload_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump()


class TraceSearchResult(TelemetrySearchModel):
    schema_version: str
    traces: tuple[TraceSearchSummary, ...]
    match_count: int = Field(..., ge=0)
    truncated: bool
    raw_payload_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "traces": [trace.safe_projection() for trace in self.traces],
            "match_count": self.match_count,
            "truncated": self.truncated,
            "raw_payload_persisted": False,
        }


def search_traces(reader: TraceReadable, query: TraceSearchQuery, *, trace_ids: tuple[str, ...]) -> TraceSearchResult:
    matches: list[TraceSearchSummary] = []
    for trace_id in trace_ids:
        projection = reader.read_trace(trace_id)
        if projection is None:
            continue
        summary = _summary_from_projection(projection)
        if _matches(summary, query):
            matches.append(summary)
        if len(matches) >= query.max_results:
            break
    total_matches = len(matches)
    truncated = any(
        reader.read_trace(trace_id) is not None and _matches(_summary_from_projection(reader.read_trace(trace_id) or {}), query)
        for trace_id in trace_ids[trace_ids.index(matches[-1].trace_id) + 1 :]
    ) if matches and total_matches >= query.max_results else False
    return TraceSearchResult(schema_version=query.schema_version, traces=tuple(matches), match_count=total_matches, truncated=truncated)


def _summary_from_projection(projection: dict[str, Any]) -> TraceSearchSummary:
    events = projection.get("events") if isinstance(projection.get("events"), list) else []
    event_fields = [event for event in events if isinstance(event, dict)]
    latest = event_fields[-1] if event_fields else {}
    return TraceSearchSummary(
        trace_id=str(projection.get("trace_id", "unknown")),
        event_count=int(projection.get("event_count", len(event_fields)) or 0),
        session_ref_id=_ref_id(latest.get("session_ref")),
        conversation_ref_id=_ref_id(latest.get("conversation_ref")),
        status=_safe_scalar(latest.get("status")),
        tool_status=_safe_scalar(latest.get("tool_status")),
        approval_status=_safe_scalar(latest.get("approval_status")),
        raw_payload_persisted=False,
    )


def _matches(summary: TraceSearchSummary, query: TraceSearchQuery) -> bool:
    return all(
        (
            query.session_ref_id is None or summary.session_ref_id == query.session_ref_id,
            query.conversation_ref_id is None or summary.conversation_ref_id == query.conversation_ref_id,
            query.status is None or summary.status == query.status,
            query.tool_status is None or summary.tool_status == query.tool_status,
            query.approval_status is None or summary.approval_status == query.approval_status,
        )
    )


def _ref_id(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    ref_id = value.get("ref_id")
    return ref_id if isinstance(ref_id, str) else None


def _safe_scalar(value: object) -> str | None:
    return value if isinstance(value, str) else None
