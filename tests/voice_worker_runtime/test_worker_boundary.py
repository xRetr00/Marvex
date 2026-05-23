from __future__ import annotations

import json

from packages.voice_worker_runtime import (
    SafeVoiceWorkerProjection,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
    VoiceWorkerEventType,
    VoiceWorkerLifecycleState,
    VoiceWorkerProcessAdapter,
    VoiceWorkerProcessSpec,
)
from packages.voice_worker_runtime.worker_main import run_worker_loop


def test_worker_config_defaults_are_local_visible_and_not_auto_started() -> None:
    config = VoiceWorkerConfig.default()

    assert config.local_only is True
    assert config.hidden_auto_start_allowed is False
    # Marvex ships always-on: the wake word is enabled by default (detection
    # still requires the installed KWS asset; no hidden auto-start of capture).
    assert config.wakeword.enabled is True
    assert config.wakeword.phrase == "Hey Marvex"
    assert config.privacy.raw_audio_persistence_allowed is False
    assert config.privacy.raw_transcript_persistence_allowed is False
    assert config.process_boundary == "local_subprocess"


def test_worker_controller_requires_explicit_start_and_tracks_heartbeat() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default())

    initial = controller.status()
    assert initial.lifecycle_state == VoiceWorkerLifecycleState.STOPPED
    assert initial.process_started is False
    assert initial.heartbeat is None

    started = controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    assert started.status.lifecycle_state == VoiceWorkerLifecycleState.RUNNING
    assert started.status.process_started is True
    assert started.event.event_type == VoiceWorkerEventType.MIC_STARTED
    assert started.status.heartbeat is not None


def test_worker_lifecycle_pause_resume_stop_and_reload_config_emit_safe_events() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default())
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    paused = controller.handle(VoiceWorkerCommand(command="pause", command_id="cmd-pause"))
    resumed = controller.handle(VoiceWorkerCommand(command="resume", command_id="cmd-resume"))
    reloaded = controller.handle(VoiceWorkerCommand(command="reload_config", command_id="cmd-reload", payload={"wakeword_enabled": True, "wakeword_threshold": 0.82}))
    stopped = controller.handle(VoiceWorkerCommand(command="stop", command_id="cmd-stop"))

    assert paused.status.lifecycle_state == VoiceWorkerLifecycleState.PAUSED
    assert resumed.status.lifecycle_state == VoiceWorkerLifecycleState.RUNNING
    assert reloaded.status.config.wakeword.enabled is True
    assert reloaded.status.config.wakeword.threshold == 0.82
    assert stopped.status.lifecycle_state == VoiceWorkerLifecycleState.STOPPED
    assert stopped.event.event_type == VoiceWorkerEventType.MIC_STOPPED
    assert json.dumps(stopped.status.safe_projection()).lower().find("raw_audio\": true") == -1


def test_worker_reload_config_updates_selected_devices_and_audio_shape() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default())

    result = controller.handle(
        VoiceWorkerCommand(
            command="reload_config",
            command_id="cmd-audio-reload",
            payload={"input_device_id": "input-default", "output_device_id": "output-default", "sample_rate": 24000, "channel_count": 1},
        )
    )

    assert result.status.config.audio.input_device_id == "input-default"
    assert result.status.config.audio.output_device_id == "output-default"
    assert result.status.config.audio.sample_rate == 24000
    assert result.event.summary["audio_config_reloaded"] is True


def test_safe_worker_projection_never_contains_raw_audio_or_transcripts() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default())
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))
    projection = SafeVoiceWorkerProjection.from_status(controller.status())
    serialized = json.dumps(projection.model_dump(mode="json")).lower()

    assert projection.raw_audio_persisted is False
    assert projection.raw_transcript_persisted is False
    assert "pcm" not in serialized
    assert "transcript_text" not in serialized


def test_process_spec_is_loopback_local_subprocess_command() -> None:
    spec = VoiceWorkerProcessSpec(port=8788)
    argv = spec.argv()

    assert argv[1:] == ("-m", "packages.voice_worker_runtime.worker_main", "--host", "127.0.0.1", "--port", "8788", "--jsonl")
    assert "0.0.0.0" not in argv


def test_process_spec_rejects_non_loopback_host() -> None:
    try:
        VoiceWorkerProcessSpec(host="0.0.0.0")
    except ValueError as exc:
        assert "loopback-only" in str(exc)
    else:
        raise AssertionError("expected non-loopback voice worker host to be rejected")


def test_process_adapter_starts_once_and_stops_safely() -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.terminated = False
            self.waited = False

        def poll(self):
            return None if not self.terminated else 0

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: int) -> None:
            assert timeout == 5
            self.waited = True

    started: list[tuple[str, ...]] = []
    processes: list[FakeProcess] = []

    def popen(argv, **kwargs):
        started.append(tuple(argv))
        process = FakeProcess()
        processes.append(process)
        return process

    adapter = VoiceWorkerProcessAdapter(spec=VoiceWorkerProcessSpec(port=8788), process_factory=popen)

    assert adapter.is_running() is False
    adapter.start()
    adapter.start()
    assert adapter.is_running() is True
    adapter.stop()

    assert len(started) == 1
    assert processes[0].terminated is True
    assert processes[0].waited is True
    assert adapter.is_running() is False


def test_worker_loop_runs_until_stopped_and_reports_status() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default())
    calls = 0

    def should_stop() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    payload = run_worker_loop(controller=controller, host="127.0.0.1", port=8788, should_stop=should_stop, sleep_seconds=0)
    final = controller.status().safe_projection()

    assert payload["status"]["lifecycle_state"] == "running"
    assert final["lifecycle_state"] == "stopped"
    assert final["process_started"] is False
