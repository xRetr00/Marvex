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


def logs_payload(log_reader: Any | None, *, max_lines: int = 200) -> dict[str, Any]:
    if log_reader is None or not hasattr(log_reader, "tail_logs"):
        logs: list[dict[str, Any]] = []
    else:
        logs = [
            _safe_log_projection(item)
            for item in log_reader.tail_logs(max_lines=max_lines)
            if isinstance(item, dict)
        ]
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
