from __future__ import annotations

import json
import time

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from tests.control_plane_api.asgi_helpers import asgi_call as _call, create_control_plane_test_app
from packages.voice_runtime import WakeWordDetectionResult
from packages.voice_worker_runtime import FakeLocalAudioAdapter, VoiceAssetManager, VoiceModelInstallRequest, VoiceWorkerBackendRuntime, VoiceWorkerConfig, VoiceWorkerControlPlaneFacade, VoiceWorkerController


def _app():
    worker = VoiceWorkerControlPlaneFacade(VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter()))
    return create_control_plane_test_app(
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



def test_control_plane_voice_worker_model_install_updates_worker_status_when_controller_owns_assets(tmp_path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter(), asset_manager=manager)
    worker = VoiceWorkerControlPlaneFacade(controller)
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        voice_worker_control=worker,
    )

    install_status, _headers, install = _call(
        app,
        "/control/voice/worker/models/install",
        method="POST",
        body={"model_id": "hey-marvex", "backend_id": "sherpa-onnx-kws", "model_kind": "wakeword", "relative_path": "wakeword/hey-marvex", "explicit_user_triggered": True},
    )
    status_code, _status_headers, status = _call(app, "/control/voice/worker")

    assert install_status == "200 OK"
    assert install["status"] == "installed"
    assert status_code == "200 OK"
    assert status["model_assets"]["required_ready_count"] == 1
    assert status["wakeword_model_status"]["status"] == "installed"


def test_control_plane_voice_worker_wakeword_supervisor_lifecycle_is_explicit_and_safe(tmp_path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)

    def wakeword_runner(_frames, asset, *, phrase: str, threshold: float):
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)

    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner),
    )
    worker = VoiceWorkerControlPlaneFacade(controller)
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        voice_worker_control=worker,
    )

    install_status, _install_headers, install = _call(
        app,
        "/control/voice/worker/models/install",
        method="POST",
        body={"model_id": "hey-marvex", "backend_id": "sherpa-onnx-kws", "model_kind": "wakeword", "relative_path": "wakeword/hey-marvex", "explicit_user_triggered": True},
    )
    _reload_status, _reload_headers, _reload = _call(app, "/control/voice/worker/reload-config", method="POST", body={"wakeword_enabled": True})
    health_status, _health_headers, health = _call(app, "/control/voice/worker/wakeword-supervisor")
    start_status, _start_headers, started = _call(app, "/control/voice/worker/wakeword-supervisor/start", method="POST")
    tick_status, _tick_headers, tick = _call(app, "/control/voice/worker/wakeword-supervisor/tick", method="POST")
    stop_status, _stop_headers, stopped = _call(app, "/control/voice/worker/wakeword-supervisor/stop", method="POST")

    assert install_status == "200 OK"
    assert install["status"] == "installed"
    assert health_status == "200 OK"
    assert health["lifecycle_state"] == "stopped"
    assert start_status == "200 OK"
    assert started["lifecycle_state"] == "running"
    assert started["hidden_auto_start_allowed"] is False
    assert tick_status == "200 OK"
    assert tick["lifecycle_state"] == "running"
    assert tick["backend_id"] == "sherpa-onnx-kws"
    assert stop_status == "200 OK"
    assert stopped["lifecycle_state"] == "stopped"
    serialized = json.dumps({"health": health, "started": started, "tick": tick, "stopped": stopped}).lower()
    assert "pcm" not in serialized
    assert "transcript_text" not in serialized


def test_voice_worker_control_plane_facade_keeps_background_wakeword_telemetry(tmp_path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="hey-marvex",
            backend_id="sherpa-onnx-kws",
            model_kind="wakeword",
            relative_path="wakeword/hey-marvex",
            explicit_user_triggered=True,
        )
    )

    def wakeword_runner(_frames, asset, *, phrase: str, threshold: float):
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)

    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner),
    )
    worker = VoiceWorkerControlPlaneFacade(controller, tick_interval_seconds=0.01)

    try:
        worker.command("start")
        deadline = time.monotonic() + 1
        status = worker.status()
        while status["telemetry"]["wakeword_detections"] < 1 and time.monotonic() < deadline:
            time.sleep(0.02)
            status = worker.status()

        assert status["wakeword_supervisor_status"]["lifecycle_state"] == "running"
        assert status["wakeword_supervisor_status"]["last_tick_at"] is not None
        assert status["wakeword_supervisor_status"]["tick_count"] >= 1
        assert status["telemetry"]["wakeword_tick_count"] >= 1
        assert status["telemetry"]["wakeword_last_tick_at"] is not None
        assert status["telemetry"]["wakeword_detections"] >= 1
    finally:
        worker.command("stop")


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
    assert assets["required_blocked_count"] >= 4
    assert remove_status == "200 OK"
    assert remove["removed"] is False


def test_control_plane_voice_worker_exposes_safe_model_catalog() -> None:
    app = _app()

    status, _headers, catalog = _call(app, "/control/voice/worker/models/catalog")

    assert status == "200 OK"
    assert catalog["raw_payload_persisted"] is False
    assert any(asset["model_id"] == "moonshine-v2" for asset in catalog["assets"])
    assert all(asset["explicit_user_triggered"] is True for asset in catalog["assets"])
