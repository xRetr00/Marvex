from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping


class AudioInputRef(VoiceRuntimeModel):
    ref_id: str = Field(..., min_length=1)
    uri: str = Field(..., min_length=1)
    format: str = Field(..., min_length=1)
    raw_audio_persisted: Literal[False] = False


class AudioFrame(VoiceRuntimeModel):
    frame_id: str = Field(..., min_length=1)
    pcm: bytes
    sample_rate: int = Field(..., gt=0)
    duration_ms: int = Field(..., gt=0)
    channel_count: int = Field(default=1, gt=0)

    def safe_projection(self) -> dict[str, object]:
        return {
            "frame_id": self.frame_id,
            "sample_rate": self.sample_rate,
            "duration_ms": self.duration_ms,
            "channel_count": self.channel_count,
            "byte_count": len(self.pcm),
            "raw_audio_persisted": False,
        }


class AudioRingBuffer(VoiceRuntimeModel):
    max_frames: int = Field(..., gt=0)
    pre_roll_ms: int = Field(default=0, ge=0)
    frames: tuple[AudioFrame, ...] = ()
    raw_audio_persisted: Literal[False] = False

    def append(self, frame: AudioFrame) -> None:
        next_frames = (*self.frames, frame)[-self.max_frames:]
        object.__setattr__(self, "frames", next_frames)

    def clear(self) -> None:
        object.__setattr__(self, "frames", ())

    def safe_projection(self) -> dict[str, object]:
        return {
            "frame_count": len(self.frames),
            "duration_ms": sum(frame.duration_ms for frame in self.frames),
            "pre_roll_ms": self.pre_roll_ms,
            "max_frames": self.max_frames,
            "raw_audio_persisted": False,
        }


class AudioCaptureRequest(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str = Field(..., min_length=1)
    source: Literal["wakeword", "manual", "push_to_talk"]
    sample_rate: int = Field(default=16000, gt=0)
    raw_audio_persisted: Literal[False] = False


class AudioCaptureResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    source: Literal["wakeword", "manual", "push_to_talk"]
    frame_count: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)
    raw_audio_persisted: Literal[False] = False

    @classmethod
    def from_request(cls, request: AudioCaptureRequest, *, frame_count: int, duration_ms: int) -> "AudioCaptureResult":
        return cls(trace_id=request.trace_id, source=request.source, frame_count=frame_count, duration_ms=duration_ms)


class NoiseFloorEstimate(VoiceRuntimeModel):
    db: float
    sample_count: int = 0


class SpeechSegment(VoiceRuntimeModel):
    segment_id: str
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    frame_count: int = Field(..., ge=0)
    noise: NoiseFloorEstimate
    raw_audio_persisted: Literal[False] = False

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


class MaxUtteranceDuration(VoiceRuntimeModel):
    duration_ms: int = Field(default=30_000, gt=0)


class SilenceCutoff(VoiceRuntimeModel):
    duration_ms: int = Field(default=800, ge=0)


class PartialTranscriptBuffer:
    def __init__(self, *, max_items: int) -> None:
        self.max_items = max_items
        self._items: list[str] = []

    def add(self, text: str) -> None:
        self._items.append(text)
        self._items = self._items[-self.max_items:]

    def safe_projection(self) -> dict[str, object]:
        return {"partial_count": len(self._items), "max_items": self.max_items, "raw_transcript_persisted": False}


class VoiceInputEvent(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1)
    source: Literal["wakeword", "manual", "push_to_talk"]
    audio_ref: AudioInputRef | None = None
    safe_summary: str | None = Field(default=None, max_length=300)
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _requires_audio_or_summary(self) -> "VoiceInputEvent":
        if self.audio_ref is None and not (self.safe_summary or "").strip():
            raise ValueError("voice input event requires audio_ref or safe_summary")
        return self

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


class VADDecision(VoiceRuntimeModel):
    is_speech: bool
    confidence: float = Field(..., ge=0, le=1)
    frame_count: int = Field(..., ge=0)
    noise_floor_db: float
    reason_code: str
    raw_audio_persisted: Literal[False] = False

    @classmethod
    def speech_started(cls, *, frame_count: int, confidence: float, noise_floor_db: float) -> "VADDecision":
        return cls(is_speech=True, confidence=confidence, frame_count=frame_count, noise_floor_db=noise_floor_db, reason_code="vad.speech_started")

    @classmethod
    def silence(cls, *, frame_count: int, confidence: float, noise_floor_db: float) -> "VADDecision":
        return cls(is_speech=False, confidence=confidence, frame_count=frame_count, noise_floor_db=noise_floor_db, reason_code="vad.silence")


class WakeWordDetectionResult:
    def __init__(self, *, detected: bool, phrase: str, confidence: float, backend_id: str, reason_code: str, cooldown_active: bool = False) -> None:
        self.detected = detected
        self.phrase = phrase
        self.confidence = confidence
        self.backend_id = backend_id
        self.reason_code = reason_code
        self.cooldown_active = cooldown_active
        self.raw_audio_persisted = False

    @classmethod
    def detected(cls, *, phrase: str, confidence: float, backend_id: str) -> "WakeWordDetectionResult":
        return cls(detected=True, phrase=phrase, confidence=confidence, backend_id=backend_id, reason_code="wakeword.detected")

    def safe_projection(self) -> dict[str, object]:
        return {
            "detected": self.detected,
            "phrase": self.phrase,
            "confidence": self.confidence,
            "backend_id": self.backend_id,
            "reason_code": self.reason_code,
            "cooldown_active": self.cooldown_active,
            "raw_audio_persisted": False,
        }


class ChunkAggregationState(VoiceRuntimeModel):
    chunk_count: int = 0
    duration_ms: int = 0
    silence_ms: int = 0
    finalized: bool = False
    reason_code: str = "chunk.collecting"
    raw_audio_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class ChunkAggregator:
    def __init__(self, *, max_utterance_ms: int, silence_cutoff_ms: int, tail_padding_ms: int) -> None:
        self.max_utterance_ms = max_utterance_ms
        self.silence_cutoff_ms = silence_cutoff_ms
        self.tail_padding_ms = tail_padding_ms
        self._duration_ms = 0
        self._silence_ms = 0
        self._chunk_count = 0

    def accept(self, frame: AudioFrame, vad: VADDecision) -> ChunkAggregationState:
        self._chunk_count += 1
        self._duration_ms += frame.duration_ms
        self._silence_ms = 0 if vad.is_speech else self._silence_ms + frame.duration_ms
        finalized = self._duration_ms >= self.max_utterance_ms or self._silence_ms >= self.silence_cutoff_ms
        reason = "chunk.collecting"
        if self._silence_ms >= self.silence_cutoff_ms:
            reason = "chunk.finalized.silence_cutoff"
        elif self._duration_ms >= self.max_utterance_ms:
            reason = "chunk.finalized.max_utterance_duration"
        return ChunkAggregationState(chunk_count=self._chunk_count, duration_ms=self._duration_ms, silence_ms=self._silence_ms, finalized=finalized, reason_code=reason)


class SpeechSegmentAssembler:
    def __init__(self, *, max_utterance_ms: int) -> None:
        self.max_utterance_ms = max_utterance_ms
        self._duration_ms = 0
        self._count = 0

    def add(self, frame: AudioFrame) -> ChunkAggregationState:
        self._count += 1
        self._duration_ms += frame.duration_ms
        finalized = self._duration_ms >= self.max_utterance_ms
        return ChunkAggregationState(chunk_count=self._count, duration_ms=self._duration_ms, finalized=finalized, reason_code="segment.max_utterance_duration" if finalized else "segment.collecting")
