from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|apikey|password|secret|token)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_AUTHORIZATION_RE = re.compile(r"(?i)\b(authorization)\b(\s*[:=]\s*)(?!bearer\s+\[redacted\])(\"[^\"]*\"|'[^']*'|[^\s,;]+)")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+([^\s,;]+)")


class LocalLogReader:
    """Read sanitized local log tails for the Control Plane API boundary."""

    def __init__(self, log_dirs: tuple[str | Path, ...]) -> None:
        self._log_dirs = tuple(Path(path).expanduser() for path in log_dirs)

    def tail_logs(self, max_lines: int = 200) -> list[dict[str, Any]]:
        max_count = max(1, min(max_lines, 2000))
        seen: set[str] = set()
        logs: list[dict[str, Any]] = []
        for directory in self._log_dirs:
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir(), key=lambda item: item.name):
                if path.suffix.lower() != ".log" or not path.is_file():
                    continue
                name = path.name
                if name in seen:
                    continue
                seen.add(name)
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                logs.append(
                    {
                        "name": sanitize_log_text(name),
                        "source": "control_plane_api",
                        "lines": [sanitize_log_text(line) for line in lines[-max_count:]],
                    }
                )
        return logs


class LocalLogWriter:
    """Append sanitized local log lines for service-owned operational events."""

    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir).expanduser()

    def append_line(self, name: str, line: str) -> None:
        safe_name = _safe_log_name(name)
        safe_line = sanitize_log_text(line)
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            with (self._log_dir / safe_name).open("a", encoding="utf-8") as handle:
                handle.write(safe_line + "\n")
        except OSError:
            return


def logs_payload(log_reader: Any | None, *, max_lines: int = 200, trace_reader: Any | None = None) -> dict[str, Any]:
    if log_reader is None or not hasattr(log_reader, "tail_logs"):
        logs: list[dict[str, Any]] = []
    else:
        logs = [
            _safe_log_projection(item)
            for item in log_reader.tail_logs(max_lines=max_lines)
            if isinstance(item, dict)
        ]
    logs.extend(_trace_log_projections(trace_reader, max_lines=max_lines))
    return {
        "schema_version": SCHEMA_VERSION,
        "logs": logs,
        "raw_log_payload_persisted": False,
    }


def _safe_log_projection(item: dict[str, Any]) -> dict[str, Any]:
    name = sanitize_log_text(str(item.get("name", "log")))
    source = sanitize_log_text(str(item.get("source", "control_plane_api")))
    raw_lines = item.get("lines", ())
    lines = raw_lines if isinstance(raw_lines, list | tuple) else ()
    return {
        "name": name,
        "source": source,
        "lines": [sanitize_log_text(str(line)) for line in lines],
    }


def sanitize_log_text(value: str) -> str:
    redacted = _BEARER_RE.sub("Bearer [redacted]", value)
    redacted = _AUTHORIZATION_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[redacted]", redacted)
    return _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[redacted]", redacted)


def _trace_log_projections(trace_reader: Any | None, *, max_lines: int) -> list[dict[str, Any]]:
    if trace_reader is None:
        return []
    trace_ids = _reader_trace_ids(trace_reader, limit=50)
    if not trace_ids:
        return []
    turn_lines: list[str] = []
    spine_lines: list[str] = []
    tool_lines: list[str] = []
    behavior_lines: list[str] = []
    followup_lines: list[str] = []
    for trace_id in trace_ids:
        try:
            envelope = trace_reader.read_trace(str(trace_id))
        except Exception:
            continue
        if not isinstance(envelope, dict):
            continue
        events = envelope.get("events")
        safe_events = [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []
        if not safe_events:
            continue
        turn_lines.extend(_turn_lines(safe_events))
        spine_lines.append(_spine_line(envelope, safe_events))
        tool_lines.extend(_field_lines(safe_events, field="tool_status"))
        behavior_lines.extend(_behavior_lines(safe_events))
        followup_lines.extend(_field_lines(safe_events, field="followup_status"))
        followup_lines.extend(_field_lines(safe_events, field="proactive_status"))
    logs: list[dict[str, Any]] = []
    for name, lines in (
        ("turns.trace.log", turn_lines),
        ("spine.trace.log", spine_lines),
        ("tools.trace.log", tool_lines),
        ("behavior.trace.log", behavior_lines),
        ("followups.trace.log", followup_lines),
    ):
        bounded_lines = [sanitize_log_text(line) for line in lines[-max_lines:]]
        if bounded_lines:
            logs.append({"name": name, "source": "trace_projection", "lines": bounded_lines})
    return logs


def _turn_lines(events: list[dict[str, Any]]) -> list[str]:
    return [
        (
            f"{_event_text(event, 'timestamp')} trace={_event_text(event, 'trace_id')} "
            f"turn={_event_text(event, 'turn_id')} stage={_event_text(event, 'stage')} "
            f"level={_event_text(event, 'level')} status={_event_text(event, 'status', default='none')} "
            f"message={_event_text(event, 'message')}"
        )
        for event in events
    ]


def _spine_line(envelope: dict[str, Any], events: list[dict[str, Any]]) -> str:
    first = events[0]
    latest = events[-1]
    return (
        f"trace={_safe_scalar_text(envelope.get('trace_id'))} "
        f"scope={_safe_scalar_text(envelope.get('scope'))} "
        f"source={_safe_scalar_text(envelope.get('source'))} "
        f"events={int(envelope.get('event_count', len(events)) or 0)} "
        f"first={_event_text(first, 'timestamp')} last={_event_text(latest, 'timestamp')} "
        f"latest_stage={_event_text(latest, 'stage')} "
        f"latest_status={_event_text(latest, 'status', default='none')}"
    )


def _behavior_lines(events: list[dict[str, Any]]) -> list[str]:
    return [
        (
            f"{_event_text(event, 'timestamp')} trace={_event_text(event, 'trace_id')} "
            f"turn={_event_text(event, 'turn_id')} stage={_event_text(event, 'stage')} "
            f"level={_event_text(event, 'level')} message={_event_text(event, 'message')}"
        )
        for event in events
    ]


def _field_lines(events: list[dict[str, Any]], *, field: str) -> list[str]:
    lines: list[str] = []
    for event in events:
        value = event.get(field)
        if not _safe_scalar(value):
            continue
        line_bits = [
            f"{_event_text(event, 'timestamp')} trace={_event_text(event, 'trace_id')}",
            f"turn={_event_text(event, 'turn_id')}",
            f"{field}={_safe_scalar_text(value)}",
            f"stage={_event_text(event, 'stage')}",
        ]
        if field == "tool_status":
            line_bits.extend(_tool_debug_bits(event))
        lines.append(" ".join(line_bits))
    return lines


def _tool_debug_bits(event: dict[str, Any]) -> list[str]:
    bits: list[str] = []
    for key in (
        "tool_boundary",
        "tool_call_count",
        "tool_loop_step",
        "tool_result_count",
        "tool_response_status",
        "tool_response_error_code",
        "tool_response_blocked",
        "tool_result_ok",
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
    ):
        value = event.get(key)
        if _safe_scalar(value):
            bits.append(f"{key}={_safe_scalar_text(value)}")
    for key in (
        "tool_call_names",
        "tool_call_ids",
        "tool_argument_keys",
        "tool_argument_value_lengths",
        "tool_result_statuses",
        "tool_result_reason_codes",
        "needs_approval_tool_ids",
        "executed_tool_ids",
        "pending_argument_keys",
    ):
        value = _safe_scalar_list_text(event.get(key))
        if value:
            bits.append(f"{key}={value}")
    return bits


def _reader_trace_ids(trace_reader: Any, *, limit: int) -> tuple[str, ...]:
    trace_ids = getattr(trace_reader, "trace_ids", None)
    if not callable(trace_ids):
        return ()
    try:
        return tuple(str(trace_id) for trace_id in trace_ids(limit=limit))[-limit:]
    except Exception:
        return ()


def _event_text(event: dict[str, Any], key: str, *, default: str = "unknown") -> str:
    value = event.get(key)
    return _safe_scalar_text(value, default=default)


def _safe_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool)


def _safe_scalar_text(value: Any, *, default: str = "unknown") -> str:
    if not _safe_scalar(value):
        return default
    return sanitize_log_text(str(value))


def _safe_scalar_list_text(value: Any) -> str | None:
    if not isinstance(value, list | tuple):
        return None
    safe_values = [sanitize_log_text(str(item)) for item in value[:24] if _safe_scalar(item)]
    return ",".join(safe_values) if safe_values else None


def _safe_log_name(name: str) -> str:
    candidate = Path(name).name
    if not candidate.endswith(".log"):
        candidate = f"{candidate}.log"
    safe = "".join(character if character.isalnum() or character in ".-_" else "_" for character in candidate)
    return safe or "marvex.log"
