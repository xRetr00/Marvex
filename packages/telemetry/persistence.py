from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from packages.contracts import ErrorCode, TraceEvent
from packages.telemetry.sanitization import REDACTED, sanitize_trace_data
from packages.telemetry.trace_reader import (
    DEFAULT_MAX_EVENTS_PER_TRACE,
    DEFAULT_MAX_MESSAGE_LENGTH,
)


TRACE_STORE_SCHEMA_VERSION = "0.1.1-draft"
TRACE_STORE_SCOPE = "local_persistence"
TRACE_STORE_SOURCE = "local_file"
DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_ROTATED_FILES = 2
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
    "model",
    "previous_response_id_present",
    "provider_response_id_present",
    "provider_tool_proposal_count",
    "provider_continuation_input_ready",
    "provider_final_response_status",
    "web_search_executed",
    "evidence_ref_count",
    "citation_validation",
}
_USAGE_KEY_PARTS = ("count", "token")
_REF_ID_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class TelemetryPersistenceError(RuntimeError):
    error_code = ErrorCode.TELEMETRY_WRITE_FAILED.value

    def __init__(self) -> None:
        super().__init__("Telemetry write failed.")


class PersistentTraceStore:
    def __init__(
        self,
        *,
        trace_file_path: str | Path,
        local_user_root: str | Path | None = None,
        max_events_per_trace: int = DEFAULT_MAX_EVENTS_PER_TRACE,
        max_message_length: int = DEFAULT_MAX_MESSAGE_LENGTH,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_rotated_files: int = DEFAULT_MAX_ROTATED_FILES,
    ) -> None:
        root = Path(local_user_root).expanduser().resolve() if local_user_root else None
        path = Path(trace_file_path).expanduser().resolve()
        if root is not None and not _is_relative_to(path, root):
            raise ValueError("trace_file_path must be local-user scoped")
        self._trace_file_path = path
        self._max_events_per_trace = max(1, max_events_per_trace)
        self._max_message_length = max(1, max_message_length)
        self._max_file_bytes = max(1, max_file_bytes)
        self._max_rotated_files = max(0, max_rotated_files)

    def emit(self, event: TraceEvent) -> None:
        record = _safe_persistent_record(event)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            self._rotate_if_needed()
            self._trace_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._trace_file_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError as exc:
            raise TelemetryPersistenceError() from exc

    def trace_ids(self, *, limit: int = 50) -> tuple[str, ...]:
        max_count = max(1, min(limit, 500))
        ordered: list[str] = []
        seen: set[str] = set()
        for record in self._iter_records():
            if not isinstance(record, dict):
                continue
            trace_id = record.get("trace_id")
            if not _valid_trace_id(trace_id):
                continue
            if trace_id in seen:
                ordered.remove(trace_id)
            seen.add(trace_id)
            ordered.append(trace_id)
        return tuple(ordered[-max_count:])

    def read_trace(self, trace_id: str) -> dict[str, Any] | None:
        events: list[TraceEvent] = []
        malformed_count = 0
        for record in self._iter_records():
            if record is None:
                malformed_count += 1
                continue
            if record.get("trace_id") != trace_id:
                continue
            try:
                events.append(TraceEvent.model_validate(record))
            except Exception:
                malformed_count += 1

        if not events:
            return None

        selected_events = events[: self._max_events_per_trace]
        return {
            "schema_version": TRACE_STORE_SCHEMA_VERSION,
            "trace_id": trace_id,
            "scope": TRACE_STORE_SCOPE,
            "source": TRACE_STORE_SOURCE,
            "events": [self._project_event(event) for event in selected_events],
            "event_count": len(selected_events),
            "truncated": len(events) > len(selected_events),
            "malformed_record_count": malformed_count,
        }

    def _iter_records(self) -> Iterable[dict[str, Any] | None]:
        for path in self._trace_files_oldest_first():
            if not path.exists() or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    yield None
                    continue
                yield record if isinstance(record, dict) else None

    def _trace_files_oldest_first(self) -> list[Path]:
        rotated = [
            self._trace_file_path.with_name(f"{self._trace_file_path.name}.{index}")
            for index in range(self._max_rotated_files, 0, -1)
        ]
        return rotated + [self._trace_file_path]

    def _rotate_if_needed(self) -> None:
        if not self._trace_file_path.exists() or self._trace_file_path.stat().st_size < self._max_file_bytes:
            return
        if self._max_rotated_files == 0:
            self._trace_file_path.unlink(missing_ok=True)
            return
        oldest = self._trace_file_path.with_name(
            f"{self._trace_file_path.name}.{self._max_rotated_files}"
        )
        oldest.unlink(missing_ok=True)
        for index in range(self._max_rotated_files - 1, 0, -1):
            source = self._trace_file_path.with_name(f"{self._trace_file_path.name}.{index}")
            target = self._trace_file_path.with_name(f"{self._trace_file_path.name}.{index + 1}")
            if source.exists():
                source.replace(target)
        self._trace_file_path.replace(self._trace_file_path.with_name(f"{self._trace_file_path.name}.1"))

    def _project_event(self, event: TraceEvent) -> dict[str, Any]:
        safe_data = sanitize_trace_data(deepcopy(event.data))
        projection: dict[str, Any] = {
            "trace_id": event.trace_id,
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat().replace("+00:00", "Z"),
            "stage": event.stage.value,
            "level": event.level.value,
            "message": _bounded_message(_safe_message(event.message), max_length=self._max_message_length),
        }
        if isinstance(safe_data, dict):
            projection.update(_safe_event_fields(safe_data))
        if "turn_id" not in projection:
            turn_id = _turn_id_from_event_id(event.event_id)
            if turn_id is not None:
                projection["turn_id"] = turn_id
        return projection


def _safe_persistent_record(event: TraceEvent) -> dict[str, Any]:
    record = {
        "schema_version": event.schema_version,
        "trace_id": event.trace_id,
        "event_id": event.event_id,
        "timestamp": event.timestamp.isoformat().replace("+00:00", "Z"),
        "stage": event.stage.value,
        "level": event.level.value,
        "message": _safe_message(event.message),
        "data": sanitize_trace_data(deepcopy(event.data)),
    }
    json.dumps(record)
    return record


def _safe_event_fields(data: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in _EVENT_PROJECTION_KEYS:
        value = data.get(key)
        if value is None or not _is_safe_scalar(value):
            continue
        fields["error_code" if key == "sanitized_error_code" else key] = value
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
        if any(part in normalized for part in _USAGE_KEY_PARTS) and isinstance(item, int | float) and not isinstance(item, bool):
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


def _normalize_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _turn_id_from_event_id(event_id: str) -> str | None:
    if ":" not in event_id:
        return None
    turn_id, _separator, _stage = event_id.partition(":")
    return turn_id or None


def _valid_trace_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and all(
        character in _REF_ID_SAFE_CHARS for character in value
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
