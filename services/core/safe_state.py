from __future__ import annotations

import json
import os
from pathlib import Path


def local_shell_state_path(env_name: str, filename: str) -> str | None:
    explicit = os.environ.get(env_name, "").strip()
    if explicit:
        return explicit
    base = (
        os.environ.get("MARVEX_DATA_DIR", "").strip()
        or os.environ.get("LOCALAPPDATA", "").strip()
        or os.environ.get("APPDATA", "").strip()
        or os.environ.get("XDG_DATA_HOME", "").strip()
        or os.path.join(os.environ.get("HOME", "") or os.environ.get("USERPROFILE", "") or os.getcwd(), ".marvex")
    )
    return os.path.join(base, "com.marvex.shell", filename)


def session_context_state_path() -> str | None:
    return local_shell_state_path("MARVEX_SESSION_CONTEXT_STATE", "session_context.json")


def conversation_entity_state_path() -> str | None:
    return local_shell_state_path("MARVEX_CONVERSATION_ENTITY_STATE", "conversation_entities.json")


def automation_pending_state_path() -> str | None:
    return local_shell_state_path("MARVEX_PENDING_AUTOMATION_STATE", "pending_automation.json")


def load_json_state(path: str | None) -> dict[str, object]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_json_state(path: str | None, payload: dict[str, object]) -> None:
    if not path:
        return
    try:
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_pending_automation_state(path: str | None) -> dict[str, dict[str, object]]:
    payload = load_json_state(path)
    rows = payload.get("pending_automation") if isinstance(payload.get("pending_automation"), dict) else payload
    if not isinstance(rows, dict):
        return {}
    pending: dict[str, dict[str, object]] = {}
    for approval_id, row in rows.items():
        if not isinstance(approval_id, str) or not isinstance(row, dict):
            continue
        sanitized = _sanitize_pending_automation(row)
        if sanitized:
            pending[approval_id] = sanitized
    return pending


def save_pending_automation_state(path: str | None, pending: dict[str, dict[str, object]]) -> None:
    save_json_state(
        path,
        {
            "schema_version": "1",
            "pending_automation": {
                approval_id: sanitized
                for approval_id, row in pending.items()
                if isinstance(approval_id, str) and (sanitized := _sanitize_pending_automation(row))
            },
            "raw_arguments_persisted": False,
        },
    )


def _sanitize_pending_automation(row: dict[str, object]) -> dict[str, object]:
    capability_id = str(row.get("capability_id") or "").strip()
    resource_type = str(row.get("resource_type") or "").strip()
    capability = str(row.get("capability") or "").strip()
    arguments = row.get("arguments")
    if not capability_id or not resource_type or not capability or not isinstance(arguments, dict):
        return {}
    sanitized = {
        "capability_id": capability_id,
        "resource_type": resource_type,
        "capability": capability,
        "arguments": _safe_automation_arguments(arguments),
    }
    for key in ("tool_id", "call_id", "response_id"):
        value = str(row.get(key) or "").strip()
        if value:
            sanitized[key] = value
    return sanitized


def _safe_automation_arguments(arguments: dict[object, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in arguments.items():
        text_key = str(key)
        lowered = text_key.lower()
        if any(marker in lowered for marker in ("authorization", "bearer", "password", "secret", "token", "raw", "prompt")):
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            safe[text_key] = value
        elif isinstance(value, dict):
            nested = _safe_automation_arguments(value)
            if nested:
                safe[text_key] = nested
    return safe
