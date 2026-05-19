from __future__ import annotations

import io
import json
from wsgiref.util import setup_testing_defaults

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore, create_control_plane_api_app
from packages.voice_runtime import DeterministicSttAdapter, DeterministicTtsAdapter, VoiceControlPlaneFacade, VoiceRuntime


def _call(app, path: str, *, method: str = "GET", token: str | None = "fake-control-token", body: dict | None = None):
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    raw = json.dumps(body or {}).encode("utf-8")
    environ["wsgi.input"] = io.BytesIO(raw)
    environ["CONTENT_LENGTH"] = str(len(raw))
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(response)


def _app():
    runtime = VoiceRuntime.with_deterministic_backends(
        stt=DeterministicSttAdapter("moonshine-v2", text="hello"),
        tts=DeterministicTtsAdapter("kokoro-onnx"),
    )
    facade = VoiceControlPlaneFacade(runtime)
    return create_control_plane_api_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        voice_control=facade,
    )


def test_control_plane_voice_status_is_auth_protected_and_safe() -> None:
    app = _app()

    unauth_status, _headers, unauth_payload = _call(app, "/control/voice", token=None)
    status, _headers, payload = _call(app, "/control/voice")

    assert unauth_status == "401 Unauthorized"
    assert unauth_payload["code"] == "AUTH_REQUIRED"
    assert status == "200 OK"
    assert payload["summary"]["main_stt_backend_id"] == "moonshine-v2"
    assert payload["summary"]["main_tts_backend_id"] == "kokoro-onnx"
    assert payload["settings"]["wakeword"]["phrase"] == "Hey Marvex"
    serialized = json.dumps(payload).lower()
    assert "authorization" not in serialized
    assert "secret" not in serialized
    assert "raw_audio\": true" not in serialized
    assert "raw_transcript\": true" not in serialized


def test_control_plane_voice_selectors_and_toggles_do_not_execute_engines() -> None:
    app = _app()

    stt_status, _headers, stt = _call(app, "/control/voice/stt/select", method="POST", body={"main_backend_id": "moonshine-v2", "fallback_backend_id": "sensevoice-small"})
    tts_status, _headers, tts = _call(app, "/control/voice/tts/select", method="POST", body={"main_backend_id": "kokoro-onnx", "fallback_backend_id": "piper-tts", "active_voice_id": "af_heart"})
    wake_status, _headers, wake = _call(app, "/control/voice/wakeword", method="POST", body={"always_listening_enabled": True})

    assert stt_status == "200 OK"
    assert stt["execution_started"] is False
    assert stt["main_backend_id"] == "moonshine-v2"
    assert tts_status == "200 OK"
    assert tts["active_voice_id"] == "af_heart"
    assert wake_status == "200 OK"
    assert wake["wakeword"]["always_listening_enabled"] is True
    assert wake["wakeword"]["visible_control_required"] is True


def test_control_plane_voice_model_download_and_voice_tests_are_explicit_and_safe() -> None:
    app = _app()

    download_status, _headers, download = _call(app, "/control/voice/models/download", method="POST", body={"model_id": "af_heart", "backend_id": "kokoro-onnx", "model_kind": "tts_voice", "source_uri": "local://voices/af_heart"})
    remove_status, _remove_headers, remove = _call(app, "/control/voice/models/remove", method="POST", body={"model_id": "af_heart", "model_kind": "tts_voice"})
    stt_test_status, _headers, stt_test = _call(app, "/control/voice/test-stt", method="POST", body={"test_id": "stt-test", "backend_id": "moonshine-v2", "sample_ref_id": "sample-1"})
    tts_test_status, _headers, tts_test = _call(app, "/control/voice/test-tts", method="POST", body={"test_id": "tts-test", "backend_id": "kokoro-onnx", "phrase": "Testing voice."})

    assert download_status == "200 OK"
    assert download["download_started"] is True
    assert download["raw_model_internals_rendered"] is False
    assert remove_status == "200 OK"
    assert remove["removed"] is True
    assert remove["raw_model_internals_rendered"] is False
    assert stt_test_status == "200 OK"
    assert stt_test["raw_audio_persisted"] is False
    assert tts_test_status == "200 OK"
    assert tts_test["raw_generated_audio_persisted"] is False


def test_control_plane_voice_rejects_unknown_actions() -> None:
    status, _headers, payload = _call(_app(), "/control/voice/unknown", method="POST")

    assert status == "404 Not Found"
    assert payload["details"]["reason"] == "voice_endpoint_not_found"
