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
    VoiceWorkerControlPlaneFacade,
    VoiceWorkerController,
    WakewordWorkerSupervisor,
    WakewordSupervisorPolicy,
)


def main() -> int:
    asset_root = Path(".marvex") / "voice-assets-smoke"
    wakeword_asset = asset_root / "wakeword" / "hey-marvex"
    wakeword_asset.mkdir(parents=True, exist_ok=True)

    manager = VoiceAssetManager(asset_root=asset_root)
    install = manager.install_local(
        VoiceModelInstallRequest(
            model_id="hey-marvex",
            backend_id="sherpa-onnx-kws",
            model_kind="wakeword",
            relative_path="wakeword/hey-marvex",
            explicit_user_triggered=True,
        )
    )
    if install.status != "installed":
        print(json.dumps({"status": "failed", "stage": "install", "install": install.model_dump(mode="json")}, indent=2))
        return 1

    calls = {"count": 0}

    def scripted_runner(frames, asset, *, phrase: str, threshold: float):
        calls["count"] += 1
        if calls["count"] == 1:
            return WakeWordDetectionResult(
                detected=False,
                phrase=phrase,
                confidence=0.0,
                backend_id=asset.backend_id,
                reason_code="wakeword_backend_runtime_error",
            )
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold + 0.05, backend_id=asset.backend_id)

    moments = [datetime(2026, 5, 20, 0, 0, 0, tzinfo=UTC)]

    def clock() -> datetime:
        moment = moments[-1]
        moments.append(moment)
        return moment

    config = VoiceWorkerConfig.default().model_copy(
        update={"wakeword": VoiceWorkerConfig.default().wakeword.model_copy(update={"enabled": True})}
    )
    audio = FakeLocalAudioAdapter()
    backend_runtime = VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=scripted_runner)
    supervisor = WakewordWorkerSupervisor(
        config=config,
        asset_manager=manager,
        backend_runtime=backend_runtime,
        audio=audio,
        policy=WakewordSupervisorPolicy(max_consecutive_failures=3, initial_backoff_ms=10, max_backoff_ms=20),
        clock=clock,
    )
    controller = VoiceWorkerController(
        config=config,
        audio=audio,
        asset_manager=manager,
        backend_runtime=backend_runtime,
        wakeword_supervisor=supervisor,
    )
    facade = VoiceWorkerControlPlaneFacade(controller)

    health_before = facade.wakeword_supervisor_health()
    started = facade.start_wakeword_supervisor()
    first_tick = facade.tick_wakeword_supervisor()
    backoff_tick = facade.tick_wakeword_supervisor()
    moments.append(moments[-1] + timedelta(milliseconds=50))
    recovery_tick = facade.tick_wakeword_supervisor()
    status_after_recovery = facade.status()
    stopped = facade.stop_wakeword_supervisor()
    controller.handle(VoiceWorkerCommand(command="stop", command_id="smoke-stop"))
    shutdown = facade.wakeword_supervisor_health()

    checks = {
        "install_uses_asset_root": install.status == "installed",
        "starts_explicitly": started["lifecycle_state"] == "running" and started["hidden_auto_start_allowed"] is False,
        "restart_backoff_after_failure": first_tick["lifecycle_state"] == "degraded" and first_tick["current_backoff_ms"] == 10,
        "health_reports_backoff": backoff_tick["exact_blocker"] == "wakeword_supervisor.backoff_active",
        "recovers_on_next_detection": recovery_tick["detected"] is True and recovery_tick["lifecycle_state"] == "running",
        "status_exposes_supervisor": status_after_recovery["wakeword_supervisor_status"]["lifecycle_state"] == "running",
        "explicit_stop_is_clean": stopped["lifecycle_state"] == "stopped",
        "worker_stop_clean_shutdown": shutdown["exact_blocker"] == "wakeword_supervisor.clean_shutdown",
    }
    payload = {
        "status": "passed" if all(checks.values()) else "failed",
        "asset_root": str(manager.asset_root),
        "checks": checks,
        "health_before": health_before,
        "started": started,
        "first_tick": first_tick,
        "backoff_tick": backoff_tick,
        "recovery_tick": recovery_tick,
        "stopped": stopped,
        "shutdown": shutdown,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
