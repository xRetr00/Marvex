from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping


class VoiceInstallStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    DOWNLOAD_BLOCKED = "download_blocked"
    ERROR = "error"


class SpeakingStyle(str, Enum):
    CALM = "calm"
    DIRECT = "direct"
    WARM = "warm"


class FillerFrequency(str, Enum):
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponsePacing(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    SLOW = "slow"


class ConcisenessLevel(str, Enum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class ConfirmationStyle(str, Enum):
    OFF = "off"
    SHORT = "short"
    EXPLICIT = "explicit"


class ErrorRecoveryStyle(str, Enum):
    BRIEF = "brief"
    GUIDED = "guided"


class SensitiveContentSpeakingPolicy(str, Enum):
    ASK = "ask"
    DENY = "deny"
    SUMMARIZE = "summarize"


class WakeWordPolicy(VoiceRuntimeModel):
    always_listening_enabled: bool = False
    explicit_control_required: Literal[True] = True
    hidden_recording_allowed: Literal[False] = False


class WakeWordConfig(VoiceRuntimeModel):
    phrase: str = "Hey Marvex"
    backend_id: str = "sherpa-onnx-kws"
    false_positive_threshold: float = Field(default=0.72, ge=0, le=1)
    cooldown_ms: int = Field(default=1500, ge=0)
    always_listening_enabled: bool = False
    push_to_talk_enabled: bool = True
    visible_control_required: Literal[True] = True


class VADBackendConfig(VoiceRuntimeModel):
    main_backend_id: str = "silero-vad"
    fallback_backend_id: str = "webrtcvad-wheels"
    aggressiveness: int = Field(default=2, ge=0, le=3)


class SilenceTimeoutPolicy(VoiceRuntimeModel):
    silence_cutoff_ms: int = Field(default=800, ge=0)


class EndOfSpeechPolicy(VoiceRuntimeModel):
    end_after_silence_ms: int = Field(default=800, ge=0)


class TailPaddingPolicy(VoiceRuntimeModel):
    tail_padding_ms: int = Field(default=240, ge=0)


class VADConfig(VoiceRuntimeModel):
    backend: VADBackendConfig = Field(default_factory=VADBackendConfig)
    silence_timeout: SilenceTimeoutPolicy = Field(default_factory=SilenceTimeoutPolicy)
    end_of_speech: EndOfSpeechPolicy = Field(default_factory=EndOfSpeechPolicy)
    tail_padding: TailPaddingPolicy = Field(default_factory=TailPaddingPolicy)
    noisy_room_handling_enabled: bool = True


class AudioRetentionPolicy(VoiceRuntimeModel):
    raw_audio_persistence_allowed: bool = False
    transcript_persistence_allowed: bool = False
    generated_audio_persistence_allowed: bool = False
    retention_reason_required: Literal[True] = True


class VoiceBackendFallbackPolicy(VoiceRuntimeModel):
    stt_auto_fallback_allowed: bool = True
    tts_auto_fallback_allowed: bool = True
    fallback_requires_safe_error: Literal[True] = True


class SentenceClampPolicy(VoiceRuntimeModel):
    max_chars: int = Field(default=180, gt=0)
    min_chars: int = Field(default=12, ge=0)
    prefer_sentence_boundary: bool = True
    stream2sentence_adapter_enabled: bool = True


class BargeInPolicy(VoiceRuntimeModel):
    enabled: bool = True
    vad_confidence_threshold: float = Field(default=0.65, ge=0, le=1)
    cancel_queued_tts: bool = True
    echo_suppression_future_seam: Literal[True] = True


class EarlySpeechPolicy(VoiceRuntimeModel):
    enabled: bool = True
    min_elapsed_ms: int = Field(default=700, ge=0)
    min_interval_ms: int = Field(default=8000, ge=0)
    stop_on_barge_in: Literal[True] = True
    fact_claims_require_evidence: Literal[True] = True


class VoicePersonalityProfile(VoiceRuntimeModel):
    profile_id: str = "default"
    speaking_style: SpeakingStyle = SpeakingStyle.DIRECT
    filler_frequency: FillerFrequency = FillerFrequency.MEDIUM
    response_pacing: ResponsePacing = ResponsePacing.BALANCED
    conciseness_level: ConcisenessLevel = ConcisenessLevel.BALANCED
    confirmation_style: ConfirmationStyle = ConfirmationStyle.SHORT
    error_recovery_style: ErrorRecoveryStyle = ErrorRecoveryStyle.BRIEF
    sensitive_content_policy: SensitiveContentSpeakingPolicy = SensitiveContentSpeakingPolicy.ASK
    active_voice_id: str = "M1"
    active_tts_speed: float = Field(default=1.05, ge=0.7, le=2.0)
    active_tts_quality_steps: int = Field(default=8, ge=5, le=12)
    auto_speak_enabled: bool = True
    speak_confirmations: bool = True

    @classmethod
    def default(cls) -> "VoicePersonalityProfile":
        return cls()

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class VoiceRuntimeConfig(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    wakeword: WakeWordConfig = Field(default_factory=WakeWordConfig)
    wakeword_policy: WakeWordPolicy = Field(default_factory=WakeWordPolicy)
    vad: VADConfig = Field(default_factory=VADConfig)
    backend_fallback: VoiceBackendFallbackPolicy = Field(default_factory=VoiceBackendFallbackPolicy)
    audio_retention: AudioRetentionPolicy = Field(default_factory=AudioRetentionPolicy)
    sentence_clamp: SentenceClampPolicy = Field(default_factory=SentenceClampPolicy)
    barge_in: BargeInPolicy = Field(default_factory=BargeInPolicy)
    early_speech: EarlySpeechPolicy = Field(default_factory=EarlySpeechPolicy)
    personality: VoicePersonalityProfile = Field(default_factory=VoicePersonalityProfile.default)

    @classmethod
    def default(cls) -> "VoiceRuntimeConfig":
        return cls()

    def safe_projection(self) -> dict[str, object]:
        payload = safe_mapping(self.model_dump(mode="json"))
        payload["hidden_recording_allowed"] = False
        return payload
