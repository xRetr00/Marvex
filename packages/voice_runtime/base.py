from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


SCHEMA_VERSION = "1"


class VoiceRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


def safe_mapping(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        normalized = key_text.lower().replace("-", "_")
        if normalized in {"pcm", "audio_bytes", "text"}:
            continue
        if normalized.startswith("raw_") and item is not False:
            continue
        if any(part in normalized for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")):
            continue
        safe[key_text] = safe_value(item)
    return safe


def safe_value(value: Any) -> Any:
    if isinstance(value, VoiceRuntimeModel):
        if hasattr(value, "safe_projection"):
            return value.safe_projection()
        return safe_mapping(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return [safe_value(item) for item in value]
    if isinstance(value, bytes):
        return {"byte_count": len(value), "raw_audio_persisted": False}
    if isinstance(value, str):
        lowered = value.lower()
        return "[redacted]" if any(part in lowered for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")) else value
    return value
