from __future__ import annotations

import io
import json
from wsgiref.util import setup_testing_defaults

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore, create_control_plane_api_app
from packages.voice_worker_runtime import FakeLocalAudioAdapter, VoiceWorkerConfig, VoiceWorkerControlPlaneFacade, VoiceWorkerController


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
    worker = VoiceWorkerControlPlaneFacade(VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter()))
    return create_control_plane_api_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        voice_worker_control=worker,
    )


def test_control_plane_voice_worker_status_and_lifecycle_are_auth_protected() -> None:
    app = _app()

    unauth_status, _headers, unauth_payload = _call(app, "/control/voice/worker", token=None)
    status, _headers, payload = _call(app, "/control/voice/worker")
    start_status, _start_headers, started = _call(app, "/control/voice/worker/start", method="POST")
    pause_status, _pause_headers, paused = _call(app, "/control/voice/worker/pause", method="POST")
    resume_status, _resume_headers, resumed = _call(app, "/control/voice/worker/resume", method="POST")
    stop_status, _stop_headers, stopped = _call(app, "/control/voice/worker/stop", method="POST")

    assert unauth_status == "401 Unauthorized"
    assert unauth_payload["code"] == "AUTH_REQUIRED"
    assert status == "200 OK"
    assert payload["lifecycle_state"] == "stopped"
    assert start_status == "200 OK"
    assert started["status"]["lifecycle_state"] == "running"
    assert pause_status == "200 OK"
    assert paused["status"]["lifecycle_state"] == "paused"
    assert resume_status == "200 OK"
    assert resumed["status"]["lifecycle_state"] == "running"
    assert stop_status == "200 OK"
    assert stopped["status"]["lifecycle_state"] == "stopped"


def test_control_plane_voice_worker_device_tests_and_backend_switches_are_safe() -> None:
    app = _app()

    devices_status, _headers, devices = _call(app, "/control/voice/worker/devices")
    mic_status, _mic_headers, mic = _call(app, "/control/voice/worker/test-mic", method="POST", body={"device_id": "input-default"})
    playback_status, _playback_headers, playback = _call(app, "/control/voice/worker/test-playback", method="POST", body={"device_id": "output-default"})
    wake_status, _wake_headers, wake = _call(app, "/control/voice/worker/test-wakeword", method="POST")
    stt_status, _stt_headers, stt = _call(app, "/control/voice/worker/stt/switch", method="POST", body={"backend_id": "sensevoice-small"})
    tts_status, _tts_headers, tts = _call(app, "/control/voice/worker/tts/switch", method="POST", body={"backend_id": "piper-tts"})
    voice_status, _voice_headers, voice = _call(app, "/control/voice/worker/voice/switch", method="POST", body={"voice_id": "af_heart"})

    assert devices_status == "200 OK"
    assert devices["input_devices"][0]["device_id"] == "input-default"
    assert mic_status == "200 OK"
    assert mic["event"]["event_type"] == "mic_started"
    assert playback_status == "200 OK"
    assert playback["status"]["playback_status"] in {"completed", "playing"}
    assert wake_status == "200 OK"
    assert wake["event"]["event_type"] in {"wakeword_detected", "error"}
    assert stt_status == "200 OK"
    assert stt["status"]["active_stt_backend_id"] == "sensevoice-small"
    assert tts_status == "200 OK"
    assert tts["status"]["active_tts_backend_id"] == "piper-tts"
    assert voice_status == "200 OK"
    assert voice["status"]["active_voice_id"] == "af_heart"
    assert "raw_audio\": true" not in json.dumps(playback).lower()


def test_control_plane_voice_worker_reload_config_selects_devices_without_audio_persistence() -> None:
    app = _app()

    status, _headers, payload = _call(
        app,
        "/control/voice/worker/reload-config",
        method="POST",
        body={"input_device_id": "input-default", "output_device_id": "output-default", "sample_rate": 24000, "channel_count": 1},
    )

    assert status == "200 OK"
    assert payload["status"]["config"]["audio"]["input_device_id"] == "input-default"
    assert payload["status"]["config"]["audio"]["output_device_id"] == "output-default"
    assert payload["event"]["summary"]["audio_config_reloaded"] is True
    assert "raw_audio\": true" not in json.dumps(payload).lower()


def test_control_plane_voice_worker_model_install_status_uses_safe_local_paths(tmp_path) -> None:
    app = _app()

    install_status, _headers, install = _call(
        app,
        "/control/voice/worker/models/install",
        method="POST",
        body={"model_id": "hey-marvex", "backend_id": "sherpa-onnx-kws", "model_kind": "wakeword", "relative_path": "wakeword/hey-marvex", "explicit_user_triggered": True},
    )
    assets_status, _assets_headers, assets = _call(app, "/control/voice/worker/assets")
    remove_status, _remove_headers, remove = _call(app, "/control/voice/worker/models/remove", method="POST", body={"model_id": "hey-marvex"})

    assert install_status == "200 OK"
    assert install["status"] == "not_installed"
    assert install["local_path_present"] is False
    assert install["exact_blocker"] == "model_path_not_found_under_voice_asset_root"
    assert assets_status == "200 OK"
    assert assets["installed_count"] == 0
    assert assets["required_blocked_count"] >= 5
    assert remove_status == "200 OK"
    assert remove["removed"] is False
