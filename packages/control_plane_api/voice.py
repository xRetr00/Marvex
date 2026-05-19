from __future__ import annotations

import json
from typing import Any

from packages.contracts import ErrorCode, ErrorEnvelope

SCHEMA_VERSION = "1"


def handle_voice_control_request(*, method: str, path: str, environ: dict[str, Any], voice_control: Any | None) -> tuple[str, dict[str, Any]] | None:
    if not path.startswith("/control/voice"):
        return None
    if voice_control is None:
        from packages.voice_runtime import VoiceControlPlaneFacade
        voice_control = VoiceControlPlaneFacade()
    if method == "GET" and path == "/control/voice":
        return "200 OK", voice_control.status()
    if method == "POST" and path == "/control/voice/stt/select":
        return "200 OK", voice_control.select_stt(_read_json(environ))
    if method == "POST" and path == "/control/voice/tts/select":
        return "200 OK", voice_control.select_tts(_read_json(environ))
    if method == "POST" and path == "/control/voice/wakeword":
        return "200 OK", voice_control.update_wakeword(_read_json(environ))
    if method == "POST" and path == "/control/voice/models/download":
        return "200 OK", voice_control.download(_read_json(environ))
    if method == "POST" and path == "/control/voice/models/remove":
        return "200 OK", voice_control.remove(_read_json(environ))
    if method == "POST" and path == "/control/voice/test-stt":
        return "200 OK", voice_control.test_stt(_read_json(environ))
    if method == "POST" and path == "/control/voice/test-tts":
        return "200 OK", voice_control.test_tts(_read_json(environ))
    return "404 Not Found", _voice_error("voice_endpoint_not_found", path)


def _read_json(environ: dict[str, Any]) -> dict[str, Any]:
    length_text = str(environ.get("CONTENT_LENGTH") or "0")
    content_length = int(length_text) if length_text.strip() else 0
    stream = environ["wsgi.input"]
    raw_body = stream.read(content_length)
    text = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)
    payload = json.loads(text or "{}")
    return payload if isinstance(payload, dict) else {}


def _voice_error(reason: str, path: str) -> dict[str, Any]:
    return ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-control-plane-voice-error",
        error_id="control-plane-voice-error",
        code=ErrorCode.NOT_FOUND,
        message="Control Plane voice endpoint not found.",
        recoverable=False,
        source="control_plane_api",
        details={"reason": reason, "path": path},
    ).model_dump(mode="json")
