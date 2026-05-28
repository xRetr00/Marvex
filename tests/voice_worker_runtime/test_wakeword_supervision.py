from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from packages.voice_runtime import WakeWordDetectionResult
from packages.voice_worker_runtime import (
    FakeLocalAudioAdapter,
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerBackendRuntime,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
    WakewordSupervisorLifecycleState,
    WakewordSupervisorPolicy,
    WakewordWorkerSupervisor,
)


def _install_hey_marvex_asset(tmp_path: Path) -> VoiceAssetManager:
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
    return manager


def _enabled_wakeword_config() -> VoiceWorkerConfig:
    default = VoiceWorkerConfig.default()
    return default.model_copy(
        update={"wakeword": default.wakeword.model_copy(update={"enabled": True})}
    )


def _disabled_wakeword_config() -> VoiceWorkerConfig:
    default = VoiceWorkerConfig.default()
    return default.model_copy(
        update={"wakeword": default.wakeword.model_copy(update={"enabled": False})}
    )


def test_wakeword_supervisor_requires_enabled_policy_and_installed_asset(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    supervisor = WakewordWorkerSupervisor(
        config=_disabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
        audio=FakeLocalAudioAdapter(),
    )

    disabled = supervisor.start()
    assert disabled.lifecycle_state == WakewordSupervisorLifecycleState.STOPPED
    assert disabled.exact_blocker == "wakeword_not_enabled"
    assert disabled.started is False
    assert disabled.hidden_auto_start_allowed is False
    assert disabled.explicit_visible_control_required is True

    supervisor.update_config(_enabled_wakeword_config())
    missing_asset = supervisor.start()
    assert missing_asset.lifecycle_state == WakewordSupervisorLifecycleState.STOPPED
    assert missing_asset.exact_blocker == "wakeword_model_not_installed"

    install_path = tmp_path / "voice-assets" / "wakeword" / "hey-marvex"
    install_path.mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="hey-marvex",
            backend_id="sherpa-onnx-kws",
            model_kind="wakeword",
            relative_path="wakeword/hey-marvex",
            explicit_user_triggered=True,
        )
    )
    ready = supervisor.start()
    assert ready.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING
    assert ready.exact_blocker is None
    assert ready.asset_ready is True


def test_wakeword_supervisor_rejects_non_explicit_user_start_and_stop(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)
    supervisor = WakewordWorkerSupervisor(
        config=_enabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
        audio=FakeLocalAudioAdapter(),
    )

    hidden_start = supervisor.start(explicit_user_triggered=False)
    assert hidden_start.lifecycle_state == WakewordSupervisorLifecycleState.STOPPED
    assert hidden_start.exact_blocker == "wakeword_supervisor.explicit_user_required"

    supervisor.start()
    hidden_stop = supervisor.stop(explicit_user_triggered=False)
    assert hidden_stop.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING
    assert hidden_stop.exact_blocker == "wakeword_supervisor.explicit_user_required"


def test_wakeword_supervisor_tick_runs_runner_on_success_path(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)
    detection_calls: list[int] = []

    def runner(frames, asset, *, phrase: str, threshold: float):
        detection_calls.append(len(frames))
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold + 0.05, backend_id=asset.backend_id)

    supervisor = WakewordWorkerSupervisor(
        config=_enabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=runner),
        audio=FakeLocalAudioAdapter(),
    )
    supervisor.start()
    tick = supervisor.tick()

    # Supervisor now captures ~1.2 s (12 x 100ms) per tick so sherpa-onnx
    # KWS has enough mel-frame context to avoid GetFrames buffer underrun.
    assert detection_calls == [12]
    assert tick.detected is True
    assert tick.exact_blocker is None
    assert tick.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING
    assert tick.consecutive_failures == 0
    assert tick.current_backoff_ms == 0


def test_wakeword_supervisor_does_not_count_silence_as_failure(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)

    def runner(frames, asset, *, phrase: str, threshold: float):
        return WakeWordDetectionResult(
            detected=False,
            phrase=phrase,
            confidence=0.0,
            backend_id=asset.backend_id,
            reason_code="wakeword.not_detected",
        )

    supervisor = WakewordWorkerSupervisor(
        config=_enabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=runner),
        audio=FakeLocalAudioAdapter(),
    )
    supervisor.start()

    tick = supervisor.tick()
    assert tick.detected is False
    assert tick.exact_blocker is None
    assert tick.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING
    assert tick.consecutive_failures == 0


def test_wakeword_supervisor_applies_backoff_and_halts_at_threshold(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)

    def failing_runner(frames, asset, *, phrase: str, threshold: float):
        return WakeWordDetectionResult(
            detected=False,
            phrase=phrase,
            confidence=0.0,
            backend_id=asset.backend_id,
            reason_code="wakeword_backend_runtime_error",
        )

    moments: list[datetime] = []

    def clock() -> datetime:
        if not moments:
            moments.append(datetime(2026, 5, 20, 0, 0, 0, tzinfo=UTC))
        else:
            moments.append(moments[-1] + timedelta(seconds=10))
        return moments[-1]

    policy = WakewordSupervisorPolicy(
        max_consecutive_failures=3,
        initial_backoff_ms=250,
        max_backoff_ms=1_000,
        auto_restart_enabled=True,
    )
    supervisor = WakewordWorkerSupervisor(
        config=_enabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=failing_runner),
        audio=FakeLocalAudioAdapter(),
        policy=policy,
        clock=clock,
    )
    supervisor.start()

    first = supervisor.tick()
    second = supervisor.tick()
    third = supervisor.tick()

    assert first.lifecycle_state == WakewordSupervisorLifecycleState.DEGRADED
    assert first.consecutive_failures == 1
    assert first.current_backoff_ms == 250
    assert first.exact_blocker == "wakeword_backend_runtime_error"

    assert second.lifecycle_state == WakewordSupervisorLifecycleState.DEGRADED
    assert second.consecutive_failures == 2
    assert second.current_backoff_ms == 500

    assert third.lifecycle_state == WakewordSupervisorLifecycleState.HALTED
    assert third.consecutive_failures == 3
    assert supervisor.health().lifecycle_state == WakewordSupervisorLifecycleState.HALTED


def test_wakeword_supervisor_skips_tick_while_backoff_active(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)

    def failing_runner(frames, asset, *, phrase: str, threshold: float):
        return WakeWordDetectionResult(
            detected=False,
            phrase=phrase,
            confidence=0.0,
            backend_id=asset.backend_id,
            reason_code="wakeword_backend_runtime_error",
        )

    base = datetime(2026, 5, 20, 0, 0, 0, tzinfo=UTC)
    moments = [base, base, base + timedelta(milliseconds=50)]
    index = {"i": 0}

    def clock() -> datetime:
        moment = moments[index["i"]]
        index["i"] = min(index["i"] + 1, len(moments) - 1)
        return moment

    policy = WakewordSupervisorPolicy(max_consecutive_failures=5, initial_backoff_ms=1_000, max_backoff_ms=5_000)
    supervisor = WakewordWorkerSupervisor(
        config=_enabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=failing_runner),
        audio=FakeLocalAudioAdapter(),
        policy=policy,
        clock=clock,
    )
    supervisor.start()
    first = supervisor.tick()
    blocked = supervisor.tick()

    assert first.lifecycle_state == WakewordSupervisorLifecycleState.DEGRADED
    assert first.current_backoff_ms == 1_000
    assert blocked.exact_blocker == "wakeword_supervisor.backoff_active"
    assert blocked.lifecycle_state == WakewordSupervisorLifecycleState.DEGRADED


def test_wakeword_supervisor_clean_shutdown_resets_state_and_records_reason(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)
    supervisor = WakewordWorkerSupervisor(
        config=_enabled_wakeword_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
        audio=FakeLocalAudioAdapter(),
    )
    supervisor.start()
    health = supervisor.clean_shutdown()

    assert health.lifecycle_state == WakewordSupervisorLifecycleState.STOPPED
    assert health.exact_blocker == "wakeword_supervisor.clean_shutdown"
    assert health.consecutive_failures == 0
    assert health.current_backoff_ms == 0


def test_controller_supervisor_methods_are_explicit_and_safe_projection_includes_status(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)
    controller = VoiceWorkerController(
        config=_enabled_wakeword_config(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
    )
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    health = controller.start_wakeword_supervisor(explicit_user_triggered=True)
    projection = controller.status().safe_projection()

    assert health.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING
    assert projection["wakeword_supervisor_status"]["lifecycle_state"] == "running"
    assert projection["wakeword_supervisor_status"]["asset_ready"] is True
    assert projection["wakeword_supervisor_status"]["hidden_auto_start_allowed"] is False
    serialized = json.dumps(projection).lower()
    assert "pcm" not in serialized
    assert "transcript_text" not in serialized


def test_controller_start_command_starts_wakeword_supervisor_when_ready(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)
    controller = VoiceWorkerController(
        config=_enabled_wakeword_config(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
    )

    result = controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    assert result.status.wakeword_supervisor_status["lifecycle_state"] == "running"
    assert result.status.wakeword_supervisor_status["started"] is True


def test_controller_wakeword_tick_records_detection_event_for_telemetry(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)

    def wakeword_runner(_frames, asset, *, phrase: str, threshold: float):
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)

    controller = VoiceWorkerController(
        config=_enabled_wakeword_config(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner),
    )
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    tick = controller.tick_wakeword_supervisor()
    projection = controller.status().safe_projection()

    assert tick.detected is True
    assert projection["recent_events"][-1]["event_type"] == "wakeword_detected"
    assert projection["telemetry"]["wakeword_detections"] == 1


def test_controller_stop_command_clean_shuts_down_supervisor(tmp_path: Path) -> None:
    manager = _install_hey_marvex_asset(tmp_path)
    controller = VoiceWorkerController(
        config=_enabled_wakeword_config(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
    )
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))
    controller.start_wakeword_supervisor(explicit_user_triggered=True)
    assert controller.wakeword_supervisor.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING

    controller.handle(VoiceWorkerCommand(command="stop", command_id="cmd-stop"))

    health = controller.wakeword_supervisor_health()
    assert health.lifecycle_state == WakewordSupervisorLifecycleState.STOPPED
    assert health.exact_blocker == "wakeword_supervisor.clean_shutdown"


def test_controller_reload_config_updates_supervisor_view_of_wakeword(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    controller = VoiceWorkerController(
        config=_disabled_wakeword_config(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
    )

    before = controller.start_wakeword_supervisor(explicit_user_triggered=True)
    assert before.exact_blocker == "wakeword_not_enabled"

    controller.handle(
        VoiceWorkerCommand(command="reload_config", command_id="cmd-reload", payload={"wakeword_enabled": True})
    )
    after_reload = controller.wakeword_supervisor_health()
    assert after_reload.exact_blocker in (None, "wakeword_not_enabled", "wakeword_model_not_installed")

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
    ready = controller.start_wakeword_supervisor(explicit_user_triggered=True)
    assert ready.lifecycle_state == WakewordSupervisorLifecycleState.RUNNING
