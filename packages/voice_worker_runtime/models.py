from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field

from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping
from packages.voice_worker_runtime.assets import InstalledModelRegistry


class VoiceWorkerLifecycleState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class VoiceWorkerEventType(str, Enum):
    MIC_STARTED = "mic_started"
    MIC_STOPPED = "mic_stopped"
    WAKEWORD_DETECTED = "wakeword_detected"
    VAD_SPEECH_STARTED = "vad_speech_started"
    VAD_SPEECH_ENDED = "vad_speech_ended"
    TRANSCRIPTION_STARTED = "transcription_started"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    ASSISTANT_TURN_STARTED = "assistant_turn_started"
    TTS_STARTED = "tts_started"
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_FINISHED = "playback_finished"
    BARGE_IN_DETECTED = "barge_in_detected"
    CANCELLED = "cancelled"
    HEALTH_REPORTED = "health_reported"
    VERSION_REPORTED = "version_reported"
    ERROR = "error"


class VoiceWorkerPrivacyConfig(VoiceRuntimeModel):
    raw_audio_persistence_allowed: Literal[False] = False
    raw_transcript_persistence_allowed: Literal[False] = False
    generated_audio_persistence_allowed: Literal[False] = False
    hidden_recording_allowed: Literal[False] = False


class VoiceWorkerWakewordConfig(VoiceRuntimeModel):
    # Marvex ships as an always-on assistant: the "Hey Marvex" wake word is
    # enabled by default and supervised 24/7 by the backend service. Detection
    # still requires the installed sherpa-onnx KWS asset; with no asset the
    # worker reports not-ready rather than listening.
    enabled: bool = True
    phrase: str = "Hey Marvex"
    backend_id: str = "sherpa-onnx-kws"
    threshold: float = Field(default=0.72, ge=0, le=1)
    cooldown_ms: int = Field(default=1500, ge=0)
    explicit_visible_control_required: Literal[True] = True


class VoiceWorkerAudioConfig(VoiceRuntimeModel):
    input_device_id: str | None = None
    output_device_id: str | None = None
    sample_rate: int = Field(default=16_000, gt=0)
    channel_count: int = Field(default=1, gt=0)
    frame_duration_ms: int = Field(default=100, gt=0)


class VoiceWorkerVADConfig(VoiceRuntimeModel):
    main_backend_id: str = "silero-vad"
    fallback_backend_id: str = "webrtcvad-wheels"
    aggressiveness: int = Field(default=2, ge=0, le=3)
    silence_timeout_ms: int = Field(default=800, ge=0)
    tail_padding_ms: int = Field(default=240, ge=0)
    max_utterance_ms: int = Field(default=30_000, gt=0)


class VoiceWorkerConfig(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    worker_id: str = "local-voice-worker"
    process_boundary: Literal["local_subprocess", "in_process_adapter", "future_daemon"] = "local_subprocess"
    local_only: Literal[True] = True
    hidden_auto_start_allowed: Literal[False] = False
    heartbeat_interval_ms: int = Field(default=1000, gt=0)
    active_stt_backend_id: str = "moonshine-v2"
    active_tts_backend_id: str = "kokoro-onnx"
    active_voice_id: str = "af_heart"
    wakeword: VoiceWorkerWakewordConfig = Field(default_factory=VoiceWorkerWakewordConfig)
    vad: VoiceWorkerVADConfig = Field(default_factory=VoiceWorkerVADConfig)
    audio: VoiceWorkerAudioConfig = Field(default_factory=VoiceWorkerAudioConfig)
    privacy: VoiceWorkerPrivacyConfig = Field(default_factory=VoiceWorkerPrivacyConfig)

    @classmethod
    def default(cls) -> "VoiceWorkerConfig":
        return cls()

    def safe_projection(self) -> dict[str, object]:
        payload = safe_mapping(self.model_dump(mode="json"))
        payload["local_only"] = True
        payload["hidden_recording_allowed"] = False
        return payload


class VoiceWorkerHeartbeat(VoiceRuntimeModel):
    heartbeat_id: str
    observed_at: str
    lifecycle_state: VoiceWorkerLifecycleState

    @classmethod
    def now(cls, *, lifecycle_state: VoiceWorkerLifecycleState) -> "VoiceWorkerHeartbeat":
        stamp = datetime.now(UTC).isoformat()
        return cls(heartbeat_id=f"voice-worker-heartbeat-{stamp}", observed_at=stamp, lifecycle_state=lifecycle_state)


class VoiceWorkerErrorEnvelope(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    error_id: str
    reason_code: str
    message: str
    recoverable: bool = True
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def safe_error(cls, *, trace_id: str, reason_code: str, message: str) -> "VoiceWorkerErrorEnvelope":
        return cls(trace_id=trace_id, error_id=f"voice-worker-error-{trace_id}", reason_code=reason_code, message=message)


class VoiceWorkerHealth(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    lifecycle_state: VoiceWorkerLifecycleState
    process_started: bool
    heartbeat_ok: bool
    local_only: Literal[True] = True
    hidden_recording_allowed: Literal[False] = False


class VoiceWorkerVersionInfo(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    worker: str
    worker_version: str = "0.2.0"
    contract_versions: dict[str, str] = Field(
        default_factory=lambda: {
            "VoiceWorkerCommand": SCHEMA_VERSION,
            "VoiceWorkerCommandResult": SCHEMA_VERSION,
            "VoiceWorkerEvent": SCHEMA_VERSION,
            "VoiceWorkerErrorEnvelope": SCHEMA_VERSION,
            "VoiceWorkerHealth": SCHEMA_VERSION,
        }
    )
    build: dict[str, Any] = Field(default_factory=dict)

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


class VoiceWorkerCommand(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    command: Literal[
        "health",
        "version",
        "cancel",
        "start",
        "stop",
        "pause",
        "resume",
        "reload_config",
        "test_mic",
        "test_wakeword",
        "test_stt",
        "test_tts",
        "test_playback",
        "download_model",
        "install_model",
        "switch_stt_backend",
        "switch_tts_backend",
        "switch_active_voice",
        "speak",
        "listen",
    ]
    command_id: str = Field(..., min_length=1)
    trace_id: str | None = Field(default=None, min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    explicit_user_triggered: Literal[True] = True


class VoiceWorkerEvent(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    event_id: str
    event_type: VoiceWorkerEventType
    trace_id: str
    summary: dict[str, Any] = Field(default_factory=dict)
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


class VoiceWorkerStatus(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    worker_id: str
    lifecycle_state: VoiceWorkerLifecycleState
    process_started: bool
    config: VoiceWorkerConfig
    heartbeat: VoiceWorkerHeartbeat | None = None
    active_stt_backend_id: str = "moonshine-v2"
    active_tts_backend_id: str = "kokoro-onnx"
    active_voice_id: str = "af_heart"
    mic_status: str = "stopped"
    playback_status: str = "stopped"
    wakeword_status: str = "disabled"
    queued_tts_count: int = 0
    recent_events: tuple[VoiceWorkerEvent, ...] = ()
    error: VoiceWorkerErrorEnvelope | None = None
    model_assets: InstalledModelRegistry
    stt_backend_status: dict[str, Any] = Field(default_factory=dict)
    tts_backend_status: dict[str, Any] = Field(default_factory=dict)
    wakeword_model_status: dict[str, Any] = Field(default_factory=dict)
    wakeword_supervisor_status: dict[str, Any] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    telemetry_summary: dict[str, Any] = Field(default_factory=dict)
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return SafeVoiceWorkerProjection.from_status(self).model_dump(mode="json")


class SafeVoiceWorkerProjection(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    worker_id: str
    lifecycle_state: VoiceWorkerLifecycleState
    process_started: bool
    heartbeat_ok: bool
    active_stt_backend_id: str
    active_tts_backend_id: str
    active_voice_id: str
    mic_status: str
    playback_status: str
    wakeword_status: str
    queued_tts_count: int
    health: dict[str, object]
    recent_events: tuple[dict[str, object], ...] = ()
    error: dict[str, object] | None = None
    model_assets: dict[str, object]
    stt_backend_status: dict[str, object] = Field(default_factory=dict)
    tts_backend_status: dict[str, object] = Field(default_factory=dict)
    wakeword_model_status: dict[str, object] = Field(default_factory=dict)
    wakeword_supervisor_status: dict[str, object] = Field(default_factory=dict)
    telemetry: dict[str, object] = Field(default_factory=dict)
    telemetry_summary: dict[str, object] = Field(default_factory=dict)
    local_only: Literal[True] = True
    hidden_recording_allowed: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def from_status(cls, status: VoiceWorkerStatus) -> "SafeVoiceWorkerProjection":
        return cls(
            worker_id=status.worker_id,
            lifecycle_state=status.lifecycle_state,
            process_started=status.process_started,
            heartbeat_ok=status.heartbeat is not None,
            active_stt_backend_id=status.active_stt_backend_id,
            active_tts_backend_id=status.active_tts_backend_id,
            active_voice_id=status.active_voice_id,
            mic_status=status.mic_status,
            playback_status=status.playback_status,
            wakeword_status=status.wakeword_status,
            queued_tts_count=status.queued_tts_count,
            health=VoiceWorkerHealth(
                lifecycle_state=status.lifecycle_state,
                process_started=status.process_started,
                heartbeat_ok=status.heartbeat is not None,
            ).model_dump(mode="json"),
            recent_events=tuple(event.safe_projection() for event in status.recent_events),
            error=status.error.model_dump(mode="json") if status.error else None,
            model_assets=status.model_assets.model_dump(mode="json"),
            stt_backend_status=safe_mapping(status.stt_backend_status),
            tts_backend_status=safe_mapping(status.tts_backend_status),
            wakeword_model_status=safe_mapping(status.wakeword_model_status),
            wakeword_supervisor_status=safe_mapping(status.wakeword_supervisor_status),
            telemetry=safe_mapping(status.telemetry),
            telemetry_summary=safe_mapping(status.telemetry_summary or status.telemetry),
        )


class VoiceWorkerCommandResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    command_id: str
    trace_id: str
    status: VoiceWorkerStatus
    event: VoiceWorkerEvent
    error: VoiceWorkerErrorEnvelope | None = None

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))
