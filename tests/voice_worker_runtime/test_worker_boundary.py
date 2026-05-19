from __future__ import annotations

import json

from packages.voice_worker_runtime import (
    SafeVoiceWorkerProjection,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
    VoiceWorkerEventType,
    VoiceWorkerLifecycleState,
)


def test_worker_config_defaults_are_local_visible_and_not_auto_started() -> None:
    config = VoiceWorkerConfig.default()

    assert config.local_only is True
    assert config.hidden_auto_start_allowed is False
    assert config.wakeword.enabled is False
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


def test_safe_worker_projection_never_contains_raw_audio_or_transcripts() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default())
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))
    projection = SafeVoiceWorkerProjection.from_status(controller.status())
    serialized = json.dumps(projection.model_dump(mode="json")).lower()

    assert projection.raw_audio_persisted is False
    assert projection.raw_transcript_persisted is False
    assert "pcm" not in serialized
    assert "transcript_text" not in serialized
