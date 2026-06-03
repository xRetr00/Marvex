from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from packages.contracts import TraceEvent
from packages.telemetry.sanitization import REDACTED, sanitize_trace_data


TRACE_READER_SCHEMA_VERSION = "0.1.1-draft"
TRACE_READER_SCOPE = "current_process"
TRACE_READER_SOURCE = "in_memory"
DEFAULT_MAX_EVENTS_PER_TRACE = 100
DEFAULT_MAX_MESSAGE_LENGTH = 300

_EVENT_PROJECTION_KEYS = {
    "turn_id",
    "status",
    "error_code",
    "sanitized_error_code",
    "finish_reason",
    "service_name",
    "service",
    "tool_status",
    "approval_status",
    "approval_request_id",
    "model",
    "previous_response_id_present",
    "provider_response_id_present",
    "provider_tool_proposal_count",
    "provider_continuation_input_ready",
    "provider_final_response_status",
    "provider_error",
    "web_search_executed",
    "evidence_ref_count",
    "citation_validation",
    "tool_boundary",
    "tool_call_count",
    "tool_loop_step",
    "tool_result_count",
    "tool_response_blocked",
    "tool_result_ok",
    "tool_response_status",
    "tool_response_error_code",
    "tool_result_reason_code",
    "tool_failure_retry_attempted",
    "reason_code",
    "pending_tool_id",
    "pending_capability_id",
    "pending_resource_type",
    "pending_call_id",
    "automation_status",
    "automation_capability_id",
    "automation_reason_code",
    "automation_live_execution",
    "automation_adapter",
    "failed_tool_status",
    "failed_tool_capability_id",
    "failed_tool_reason_code",
}
_SAFE_SCALAR_LIST_EVENT_KEYS = {
    "tool_call_names",
    "tool_call_ids",
    "tool_argument_keys",
    "tool_argument_value_lengths",
    "tool_result_statuses",
    "tool_result_reason_codes",
    "needs_approval_tool_ids",
    "executed_tool_ids",
    "pending_argument_keys",
}
_USAGE_KEY_PARTS = (
    "count",
    "token",
)
_REF_ID_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class InMemoryTraceReader:
    def __init__(
        self,
        *,
        max_events_per_trace: int = DEFAULT_MAX_EVENTS_PER_TRACE,
        max_message_length: int = DEFAULT_MAX_MESSAGE_LENGTH,
    ) -> None:
        self._events_by_trace_id: dict[str, list[TraceEvent]] = defaultdict(list)
        self._max_events_per_trace = max(1, max_events_per_trace)
        self._max_message_length = max(1, max_message_length)

    def emit(self, event: TraceEvent) -> None:
        self._events_by_trace_id[event.trace_id].append(event)

    def trace_ids(self, *, limit: int = 50) -> tuple[str, ...]:
        max_count = max(1, min(limit, 500))
        return tuple(self._events_by_trace_id.keys())[-max_count:]

    def read_trace(self, trace_id: str) -> dict[str, Any] | None:
        events = self._events_by_trace_id.get(trace_id)
        if not events:
            return None

        selected_events = events[: self._max_events_per_trace]
        return {
            "schema_version": TRACE_READER_SCHEMA_VERSION,
            "trace_id": trace_id,
            "scope": TRACE_READER_SCOPE,
            "source": TRACE_READER_SOURCE,
            "events": [self._project_event(event) for event in selected_events],
            "event_count": len(selected_events),
            "truncated": len(events) > len(selected_events),
        }

    def _project_event(self, event: TraceEvent) -> dict[str, Any]:
        safe_data = sanitize_trace_data(deepcopy(event.data))
        projection: dict[str, Any] = {
            "trace_id": event.trace_id,
            "event_id": event.event_id,
            "timestamp": _format_timestamp(event.timestamp),
            "stage": event.stage.value,
            "level": event.level.value,
            "message": _bounded_message(
                _safe_message(event.message),
                max_length=self._max_message_length,
            ),
        }
        if isinstance(safe_data, dict):
            projection.update(_safe_event_fields(safe_data))
        if "turn_id" not in projection:
            turn_id = _turn_id_from_event_id(event.event_id)
            if turn_id is not None:
                projection["turn_id"] = turn_id
        return projection


def _safe_event_fields(data: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in _EVENT_PROJECTION_KEYS:
        if key not in data:
            continue
        value = data.get(key)
        if value is None:
            continue
        if _is_safe_scalar(value):
            output_key = "error_code" if key == "sanitized_error_code" else key
            fields[output_key] = value
    for key in _SAFE_SCALAR_LIST_EVENT_KEYS:
        if key not in data:
            continue
        value = _safe_scalar_list(data.get(key))
        if value:
            fields[key] = value
    if "usage" in data:
        usage = _safe_usage(data["usage"])
        if usage:
            fields["usage"] = usage
    session_ref = _safe_ref(data.get("session_ref"), expected_ref_type="session")
    if session_ref is not None:
        fields["session_ref"] = session_ref
    conversation_ref = _safe_ref(
        data.get("conversation_ref"),
        expected_ref_type="conversation",
    )
    if conversation_ref is not None:
        fields["conversation_ref"] = conversation_ref
    if "service" in fields and "service_name" not in fields:
        fields["service_name"] = fields.pop("service")
    else:
        fields.pop("service", None)
    return fields


def _safe_ref(value: Any, *, expected_ref_type: str) -> dict[str, str] | None:
    if not isinstance(value, dict) or set(value) != {"ref_type", "ref_id"}:
        return None
    ref_type = value.get("ref_type")
    ref_id = value.get("ref_id")
    if ref_type != expected_ref_type or not isinstance(ref_id, str):
        return None
    if not ref_id or ref_id != ref_id.strip():
        return None
    if any(character not in _REF_ID_SAFE_CHARS for character in ref_id):
        return None
    return {"ref_type": expected_ref_type, "ref_id": ref_id}


def _safe_usage(value: Any) -> dict[str, int | float] | None:
    if not isinstance(value, dict):
        return None
    usage: dict[str, int | float] = {}
    for key, item in value.items():
        normalized = _normalize_key(key)
        if (
            any(part in normalized for part in _USAGE_KEY_PARTS)
            and isinstance(item, int | float)
            and not isinstance(item, bool)
        ):
            usage[str(key)] = item
    return usage or None


def _safe_message(message: str) -> str:
    sanitized = sanitize_trace_data({"message": message})
    value = sanitized.get("message") if isinstance(sanitized, dict) else REDACTED
    return value if isinstance(value, str) else REDACTED


def _bounded_message(message: str, *, max_length: int) -> str:
    if len(message) <= max_length:
        return message
    if max_length <= 3:
        return "." * max_length
    return f"{message[: max_length - 3]}..."


def _is_safe_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _safe_scalar_list(value: Any) -> list[str | int | float | bool] | None:
    if not isinstance(value, list | tuple):
        return None
    safe_items: list[str | int | float | bool] = []
    for item in value[:24]:
        if isinstance(item, str | int | float | bool):
            safe_items.append(item)
    return safe_items or None


def _normalize_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _format_timestamp(value: object) -> str:
    timestamp = value.isoformat()
    return timestamp.replace("+00:00", "Z")


def _turn_id_from_event_id(event_id: str) -> str | None:
    if ":" not in event_id:
        return None
    turn_id, _separator, _stage = event_id.partition(":")
    return turn_id or None
