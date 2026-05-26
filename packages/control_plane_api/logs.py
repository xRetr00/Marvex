from __future__ import annotations

from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"
UNSAFE_TEXT_PARTS = ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")


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
    lowered = value.lower()
    return "[redacted]" if any(part in lowered for part in UNSAFE_TEXT_PARTS) else value


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
        lines.append(
            (
                f"{_event_text(event, 'timestamp')} trace={_event_text(event, 'trace_id')} "
                f"turn={_event_text(event, 'turn_id')} {field}={_safe_scalar_text(value)} "
                f"stage={_event_text(event, 'stage')}"
            )
        )
    return lines


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


def _safe_log_name(name: str) -> str:
    candidate = Path(name).name
    if not candidate.endswith(".log"):
        candidate = f"{candidate}.log"
    safe = "".join(character if character.isalnum() or character in ".-_" else "_" for character in candidate)
    return safe or "marvex.log"
