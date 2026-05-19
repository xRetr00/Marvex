from __future__ import annotations

import json
from typing import Any

from packages.contracts import ErrorCode, ErrorEnvelope

SCHEMA_VERSION = "1"


def handle_voice_control_request(*, method: str, path: str, environ: dict[str, Any], voice_control: Any | None, voice_worker_control: Any | None = None) -> tuple[str, dict[str, Any]] | None:
    if not path.startswith("/control/voice"):
        return None
    if path.startswith("/control/voice/worker"):
        if voice_worker_control is None:
            from packages.voice_worker_runtime import VoiceWorkerControlPlaneFacade
            voice_worker_control = VoiceWorkerControlPlaneFacade()
        if method == "GET" and path == "/control/voice/worker":
            return "200 OK", voice_worker_control.status()
        if method == "GET" and path == "/control/voice/worker/devices":
            return "200 OK", voice_worker_control.devices()
        if method == "GET" and path == "/control/voice/worker/assets":
            return "200 OK", voice_worker_control.assets_status()
        worker_commands = {
            "/control/voice/worker/start": "start",
            "/control/voice/worker/stop": "stop",
            "/control/voice/worker/pause": "pause",
            "/control/voice/worker/resume": "resume",
            "/control/voice/worker/reload-config": "reload_config",
            "/control/voice/worker/test-mic": "test_mic",
            "/control/voice/worker/test-wakeword": "test_wakeword",
            "/control/voice/worker/test-stt": "test_stt",
            "/control/voice/worker/test-tts": "test_tts",
            "/control/voice/worker/test-playback": "test_playback",
            "/control/voice/worker/stt/switch": "switch_stt_backend",
            "/control/voice/worker/tts/switch": "switch_tts_backend",
            "/control/voice/worker/voice/switch": "switch_active_voice",
        }
        if method == "POST" and path in worker_commands:
            return "200 OK", voice_worker_control.command(worker_commands[path], _read_json(environ))
        if method == "POST" and path == "/control/voice/worker/models/install":
            return "200 OK", voice_worker_control.install_model_voice(_read_json(environ))
        if method == "POST" and path == "/control/voice/worker/models/remove":
            return "200 OK", voice_worker_control.remove_model_voice(_read_json(environ))
        return "404 Not Found", _voice_error("voice_worker_endpoint_not_found", path)
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
    if method == "POST" and path == "/control/voice/vad":
        return "200 OK", voice_control.update_vad(_read_json(environ))
    if method == "POST" and path == "/control/voice/barge-in":
        return "200 OK", voice_control.update_barge_in(_read_json(environ))
    if method == "POST" and path == "/control/voice/early-speech":
        return "200 OK", voice_control.update_early_speech(_read_json(environ))
    if method == "POST" and path == "/control/voice/personality":
        return "200 OK", voice_control.update_personality(_read_json(environ))
    if method == "POST" and path == "/control/voice/retention":
        return "200 OK", voice_control.update_retention(_read_json(environ))
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
