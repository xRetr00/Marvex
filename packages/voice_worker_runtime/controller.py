from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from packages.voice_runtime import ChunkAggregator, VADDecision, VoicePlaybackResult, VoiceRuntime, VoiceTurnRequest

from .assets import VoiceAssetManager, VoiceModelInstallRequest
from .audio import FakeLocalAudioAdapter, LocalAudioAdapter, PlaybackAdapterResult
from .models import (
    VoiceWorkerCommand,
    VoiceWorkerCommandResult,
    VoiceWorkerConfig,
    VoiceWorkerErrorEnvelope,
    VoiceWorkerEvent,
    VoiceWorkerEventType,
    VoiceWorkerHeartbeat,
    VoiceWorkerLifecycleState,
    VoiceWorkerStatus,
)


class VoiceWorkerTurnRunResult:
    def __init__(self, *, turn: Any, events: tuple[VoiceWorkerEvent, ...], playback: PlaybackAdapterResult) -> None:
        self.turn = turn
        self.events = events
        self.playback = playback

    def safe_projection(self) -> dict[str, object]:
        return {"turn_status": self.turn.status, "event_count": len(self.events), "playback_status": self.playback.status, "raw_audio_persisted": False, "raw_transcript_persisted": False}


class VoiceWorkerController:
    def __init__(self, *, config: VoiceWorkerConfig | None = None, audio: LocalAudioAdapter | None = None, voice_runtime: VoiceRuntime | None = None, asset_manager: VoiceAssetManager | None = None) -> None:
        self.config = config or VoiceWorkerConfig.default()
        self.audio = audio or FakeLocalAudioAdapter()
        self.voice_runtime = voice_runtime or VoiceRuntime()
        self.asset_manager = asset_manager or VoiceAssetManager(asset_root=Path(".marvex") / "voice-assets")
        self._state = VoiceWorkerLifecycleState.STOPPED
        self._heartbeat: VoiceWorkerHeartbeat | None = None
        self._events: list[VoiceWorkerEvent] = []
        self._playback_status = "stopped"
        self._queued_tts_count = 0
        self._error: VoiceWorkerErrorEnvelope | None = None

    def status(self) -> VoiceWorkerStatus:
        return VoiceWorkerStatus(
            worker_id=self.config.worker_id,
            lifecycle_state=self._state,
            process_started=self._state in {VoiceWorkerLifecycleState.RUNNING, VoiceWorkerLifecycleState.PAUSED},
            config=self.config,
            heartbeat=self._heartbeat,
            active_stt_backend_id=self.config.active_stt_backend_id,
            active_tts_backend_id=self.config.active_tts_backend_id,
            active_voice_id=self.config.active_voice_id,
            mic_status="started" if self._state in {VoiceWorkerLifecycleState.RUNNING, VoiceWorkerLifecycleState.PAUSED} else "stopped",
            playback_status=self._playback_status,
            wakeword_status="enabled" if self.config.wakeword.enabled else "disabled",
            queued_tts_count=self._queued_tts_count,
            recent_events=tuple(self._events[-20:]),
            error=self._error,
        )

    def handle(self, command: VoiceWorkerCommand) -> VoiceWorkerCommandResult:
        handler = getattr(self, f"_handle_{command.command}")
        event = handler(command)
        return VoiceWorkerCommandResult(command_id=command.command_id, status=self.status(), event=event, error=self._error)

    def run_manual_turn(self, *, trace_id: str, assistant_turn_runner: Callable[[str], Any], policy_decider: Callable[[str], Any]) -> VoiceWorkerTurnRunResult:
        frames = tuple(self.audio.capture_frames(device_id=self.config.audio.input_device_id, sample_rate=self.config.audio.sample_rate, channel_count=self.config.audio.channel_count, frame_count=4))
        aggregator = ChunkAggregator(max_utterance_ms=self.config.vad.max_utterance_ms, silence_cutoff_ms=self.config.vad.silence_timeout_ms, tail_padding_ms=self.config.vad.tail_padding_ms)
        for frame in frames:
            aggregator.accept(frame, VADDecision.speech_started(frame_count=1, confidence=0.8, noise_floor_db=-45))
        events = (
            self._record(VoiceWorkerEventType.VAD_SPEECH_STARTED, trace_id=trace_id, summary={"frame_count": len(frames)}),
            self._record(VoiceWorkerEventType.VAD_SPEECH_ENDED, trace_id=trace_id, summary={"duration_ms": sum(frame.duration_ms for frame in frames)}),
            self._record(VoiceWorkerEventType.TRANSCRIPTION_STARTED, trace_id=trace_id),
        )
        turn = self.voice_runtime.run_voice_turn(VoiceTurnRequest.manual(trace_id=trace_id, audio_ref_id=f"memory://voice/captured/{trace_id}"), assistant_turn_runner=assistant_turn_runner, policy_decider=policy_decider)
        more_events = (
            self._record(VoiceWorkerEventType.TRANSCRIPTION_COMPLETED, trace_id=trace_id, summary={"backend_id": turn.transcription.backend_id, "text_present": bool(turn.transcription.text)}),
            self._record(VoiceWorkerEventType.ASSISTANT_TURN_STARTED, trace_id=trace_id, summary={"policy_decision": turn.policy_decision.decision}),
            self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=trace_id, summary={"backend_id": turn.speech.backend_id if turn.speech else "none"}),
            self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id),
        )
        if turn.speech and turn.speech.audio_ref:
            self.audio.play_audio(device_id=self.config.audio.output_device_id, audio_ref=turn.speech.audio_ref, sample_rate=turn.speech.sample_rate)
        playback = self.audio.stop_playback()
        self._playback_status = "completed"
        final = self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id)
        turn.playback = VoicePlaybackResult(trace_id=trace_id, status="completed", audio_ref=turn.playback.audio_ref, backend_id=turn.playback.backend_id)  # type: ignore[misc]
        return VoiceWorkerTurnRunResult(turn=turn, events=events + more_events + (final,), playback=playback.model_copy(update={"status": "completed"}))

    def _handle_start(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self._state = VoiceWorkerLifecycleState.RUNNING
        self._heartbeat = VoiceWorkerHeartbeat.now(lifecycle_state=self._state)
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=command.command_id, summary={"explicit_user_triggered": True})

    def _handle_stop(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.audio.stop_playback()
        self._state = VoiceWorkerLifecycleState.STOPPED
        self._playback_status = "stopped"
        self._queued_tts_count = 0
        return self._record(VoiceWorkerEventType.MIC_STOPPED, trace_id=command.command_id)

    def _handle_pause(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self._state = VoiceWorkerLifecycleState.PAUSED
        self._heartbeat = VoiceWorkerHeartbeat.now(lifecycle_state=self._state)
        return self._record(VoiceWorkerEventType.MIC_STOPPED, trace_id=command.command_id, summary={"paused": True})

    def _handle_resume(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self._state = VoiceWorkerLifecycleState.RUNNING
        self._heartbeat = VoiceWorkerHeartbeat.now(lifecycle_state=self._state)
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=command.command_id, summary={"resumed": True})

    def _handle_reload_config(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        wakeword = self.config.wakeword.model_copy(update={
            "enabled": bool(command.payload.get("wakeword_enabled", self.config.wakeword.enabled)),
            "threshold": float(command.payload.get("wakeword_threshold", self.config.wakeword.threshold)),
        })
        self.config = self.config.model_copy(update={"wakeword": wakeword})
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=command.command_id, summary={"config_reloaded": True})

    def _handle_test_mic(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        level = self.audio.test_mic_level(device_id=command.payload.get("device_id") or self.config.audio.input_device_id, duration_ms=250)
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=command.command_id, summary=level.model_dump(mode="json"))

    def _handle_test_playback(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        playback = self.audio.play_audio(device_id=command.payload.get("device_id") or self.config.audio.output_device_id, audio_ref="memory://voice/test/playback", sample_rate=24_000)
        if command.payload.get("simulate_barge_in"):
            playback = self.audio.interrupt_playback(reason_code="barge_in.user_speech_detected")
            self._playback_status = "interrupted"
            self._queued_tts_count = 0
            return self._record(VoiceWorkerEventType.BARGE_IN_DETECTED, trace_id=command.command_id, summary=playback.model_dump(mode="json"))
        self._playback_status = "completed"
        return self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=command.command_id, summary=playback.model_dump(mode="json"))

    def _handle_test_wakeword(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        if not self.config.wakeword.enabled:
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=command.command_id, reason_code="wakeword_not_enabled", message="Wakeword is disabled or model assets are not ready.")
            return self._record(VoiceWorkerEventType.ERROR, trace_id=command.command_id, summary={"wakeword_ready": False})
        return self._record(VoiceWorkerEventType.WAKEWORD_DETECTED, trace_id=command.command_id, summary={"phrase": self.config.wakeword.phrase, "threshold": self.config.wakeword.threshold})

    def _handle_test_stt(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        return self._record(VoiceWorkerEventType.TRANSCRIPTION_COMPLETED, trace_id=command.command_id, summary={"backend_id": self.config.active_stt_backend_id, "status": "blocked_without_model_asset"})

    def _handle_test_tts(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        return self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=command.command_id, summary={"backend_id": self.config.active_tts_backend_id, "voice_id": self.config.active_voice_id, "status": "blocked_without_voice_asset"})

    def _handle_install_model(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        result = self.asset_manager.install_local(VoiceModelInstallRequest.model_validate(command.payload))
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=command.command_id, summary=result.model_dump(mode="json"))

    def _handle_switch_stt_backend(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.config = self.config.model_copy(update={"active_stt_backend_id": str(command.payload.get("backend_id") or self.config.active_stt_backend_id)})
        return self._record(VoiceWorkerEventType.TRANSCRIPTION_STARTED, trace_id=command.command_id, summary={"active_stt_backend_id": self.config.active_stt_backend_id})

    def _handle_switch_tts_backend(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.config = self.config.model_copy(update={"active_tts_backend_id": str(command.payload.get("backend_id") or self.config.active_tts_backend_id)})
        return self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=command.command_id, summary={"active_tts_backend_id": self.config.active_tts_backend_id})

    def _handle_switch_active_voice(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.config = self.config.model_copy(update={"active_voice_id": str(command.payload.get("voice_id") or self.config.active_voice_id)})
        return self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=command.command_id, summary={"active_voice_id": self.config.active_voice_id})

    def _record(self, event_type: VoiceWorkerEventType, *, trace_id: str, summary: dict[str, Any] | None = None) -> VoiceWorkerEvent:
        event = VoiceWorkerEvent(event_id=f"voice-worker-event-{len(self._events) + 1}", event_type=event_type, trace_id=trace_id, summary=summary or {})
        self._events.append(event)
        return event
