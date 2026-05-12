from __future__ import annotations

import json
import re
from typing import Any


REDACTED = "[REDACTED]"

_FORBIDDEN_KEY_NAMES = {
    "apikey",
    "authorization",
    "bearer",
    "conversation",
    "conversationid",
    "fullprompt",
    "messages",
    "parsedpayload",
    "password",
    "previousresponseid",
    "prompt",
    "providerresponseid",
    "rawmetadata",
    "rawoutput",
    "rawpreview",
    "rawprovideroutput",
    "rawresponse",
    "responseid",
    "secret",
    "sessionid",
    "systemprompt",
    "threadid",
    "token",
    "transcript",
}
_FORBIDDEN_KEY_PARTS = (
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
)
_SAFE_USAGE_COUNT_KEYS = {
    "inputcount",
    "outputcount",
    "prompttokens",
    "completiontokens",
    "totaltokens",
    "totalcount",
}
_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_FORBIDDEN_ERROR_CODE_PARTS = {"SECRET", "PASSWORD", "TOKEN", "API_KEY", "BEARER"}
_UNSAFE_STRING_TERMS = (
    "api key",
    "api_key",
    "authorization",
    "bearer",
    "exception",
    "full prompt",
    "jsondecodeerror",
    "password",
    "provider output",
    "raw provider",
    "secret",
    "system prompt",
    "token",
    "traceback",
    "validationerror",
)


def sanitize_trace_data(data: Any) -> Any:
    _assert_json_compatible(data)
    return _sanitize_value(data, parent_key=None)


def assert_trace_data_safe(data: Any) -> None:
    sanitized = sanitize_trace_data(data)
    if sanitized != data:
        raise ValueError("trace data contains unsafe telemetry fields")


def _sanitize_value(value: Any, *, parent_key: str | None) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if _key_is_unsafe(key, parent_key=parent_key)
                else _sanitize_value(item, parent_key=str(key))
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, parent_key=parent_key) for item in value]
    if isinstance(value, str):
        return REDACTED if _string_is_unsafe(value, parent_key=parent_key) else value
    return value


def _key_is_unsafe(key: object, *, parent_key: str | None) -> bool:
    normalized = _normalize_key(key)
    parent = _normalize_key(parent_key) if parent_key is not None else None
    if parent == "usage" and normalized in _SAFE_USAGE_COUNT_KEYS:
        return False
    return normalized in _FORBIDDEN_KEY_NAMES or any(
        part in normalized for part in _FORBIDDEN_KEY_PARTS
    )


def _string_is_unsafe(value: str, *, parent_key: str | None) -> bool:
    normalized_parent = _normalize_key(parent_key) if parent_key is not None else ""
    if normalized_parent == "sanitizederrorcode":
        return _error_code_is_unsafe(value)
    lowered = value.lower()
    return _looks_like_full_json(value) or any(term in lowered for term in _UNSAFE_STRING_TERMS)


def _error_code_is_unsafe(value: str) -> bool:
    return _ERROR_CODE_PATTERN.fullmatch(value) is None or any(
        part in value for part in _FORBIDDEN_ERROR_CODE_PARTS
    )


def _normalize_key(value: object) -> str:
    text = str(value)
    text = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", text)
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _looks_like_full_json(value: str) -> bool:
    stripped = value.strip()
    return (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    )


def _assert_json_compatible(data: Any) -> None:
    try:
        json.dumps(data)
    except (TypeError, ValueError) as exc:
        raise ValueError("trace data must be JSON-compatible") from exc
