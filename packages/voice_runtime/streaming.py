from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
import re
from typing import Literal

from pydantic import Field

from packages.voice_runtime.base import VoiceRuntimeModel, safe_mapping
from packages.voice_runtime.config import BargeInPolicy, EarlySpeechPolicy, SentenceClampPolicy


class StreamingTextChunk(VoiceRuntimeModel):
    text: str
    index: int = Field(..., ge=0)
    final: bool = False


class SpokenChunk(VoiceRuntimeModel):
    chunk_id: str
    text: str
    index: int
    raw_text_persisted: Literal[False] = False


class ChunkPlaybackState(VoiceRuntimeModel):
    chunk_id: str
    backend_id: str
    status: Literal["queued", "playing", "completed", "interrupted"]
    raw_audio_persisted: Literal[False] = False

    @classmethod
    def playing(cls, *, chunk_id: str, backend_id: str) -> "ChunkPlaybackState":
        return cls(chunk_id=chunk_id, backend_id=backend_id, status="playing")


class SentenceBoundaryDetector:
    def __init__(self, policy: SentenceClampPolicy, *, module_loader: Callable[[str], object] | None = None) -> None:
        self.policy = policy
        self._buffer = ""
        self._next = 0
        self._module_loader = module_loader or import_module

    def accept(self, chunk: StreamingTextChunk) -> tuple[SpokenChunk, ...]:
        self._buffer += chunk.text
        if chunk.final:
            packaged = self._stream2sentence_chunks()
            if packaged:
                return packaged
        boundary = re.search(r"[.!?](\s|$)", self._buffer)
        if boundary is None and len(self._buffer) < self.policy.max_chars and not chunk.final:
            return ()
        end = boundary.end() if boundary else min(len(self._buffer), self.policy.max_chars)
        text = self._buffer[:end].strip()
        if len(text) < self.policy.min_chars and not chunk.final:
            return ()
        self._buffer = self._buffer[end:].lstrip()
        spoken = SpokenChunk(chunk_id=f"spoken-{self._next}", text=text, index=self._next)
        self._next += 1
        return (spoken,)

    def _stream2sentence_chunks(self) -> tuple[SpokenChunk, ...]:
        try:
            module = self._module_loader("stream2sentence")
            sentences = tuple(str(sentence).strip() for sentence in module.generate_sentences((self._buffer,)) if str(sentence).strip())  # type: ignore[attr-defined]
        except Exception:
            return ()
        if not sentences:
            return ()
        self._buffer = ""
        chunks = []
        for sentence in sentences:
            chunks.append(SpokenChunk(chunk_id=f"spoken-{self._next}", text=sentence[: self.policy.max_chars], index=self._next))
            self._next += 1
        return tuple(chunks)


class TTSQueueCancelResult(VoiceRuntimeModel):
    canceled_count: int
    reason_code: str


class TTSQueue:
    def __init__(self) -> None:
        self._items: list[SpokenChunk] = []

    @property
    def pending_count(self) -> int:
        return len(self._items)

    def enqueue(self, chunk: SpokenChunk) -> None:
        self._items.append(chunk)

    def cancel_all(self, *, reason_code: str) -> TTSQueueCancelResult:
        count = len(self._items)
        self._items.clear()
        return TTSQueueCancelResult(canceled_count=count, reason_code=reason_code)


class UserSpeechDuringPlaybackEvent(VoiceRuntimeModel):
    trace_id: str
    confidence: float = Field(..., ge=0, le=1)
    playback_chunk_id: str
    raw_audio_persisted: Literal[False] = False


class AssistantSpeechCancelState(VoiceRuntimeModel):
    playback_stopped: bool
    queued_chunks_canceled: bool
    early_speech_stopped: bool


class PlaybackInterruptRequest(VoiceRuntimeModel):
    trace_id: str
    chunk_id: str
    reason_code: str


class PlaybackInterruptResult(VoiceRuntimeModel):
    trace_id: str
    interrupted: bool
    reason_code: str
    cancel_state: AssistantSpeechCancelState
    raw_audio_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


BargeInEvent = UserSpeechDuringPlaybackEvent


class BargeInDetector:
    def __init__(self, policy: BargeInPolicy) -> None:
        self.policy = policy

    def evaluate(self, event: UserSpeechDuringPlaybackEvent, playback: ChunkPlaybackState) -> PlaybackInterruptResult:
        should_interrupt = self.policy.enabled and playback.status == "playing" and event.confidence >= self.policy.vad_confidence_threshold
        return PlaybackInterruptResult(
            trace_id=event.trace_id,
            interrupted=should_interrupt,
            reason_code="barge_in.user_speech_detected" if should_interrupt else "barge_in.not_triggered",
            cancel_state=AssistantSpeechCancelState(playback_stopped=should_interrupt, queued_chunks_canceled=should_interrupt and self.policy.cancel_queued_tts, early_speech_stopped=should_interrupt),
        )


class EarlySpeechTrigger(VoiceRuntimeModel):
    intent_kind: str
    elapsed_ms: int = Field(..., ge=0)
    previous_filler_elapsed_ms: int | None = Field(default=None, ge=0)


class EarlySpeechEvent(VoiceRuntimeModel):
    text: str
    intent_kind: str
    claims_facts_without_evidence: Literal[False] = False
    raw_payload_persisted: Literal[False] = False


class EarlySpeechResult(VoiceRuntimeModel):
    should_speak: bool
    text: str | None = None
    event: EarlySpeechEvent | None = None
    reason_code: str
    claims_facts_without_evidence: Literal[False] = False


class ThinkingFillerTemplate(VoiceRuntimeModel):
    intent_kind: str
    text: str


class DidYouKnowCandidate(VoiceRuntimeModel):
    text: str
    evidence_ref: str | None = None


class SearchProgressSpeech(VoiceRuntimeModel):
    text: str = "I am searching for the latest information."


class ToolProgressSpeech(VoiceRuntimeModel):
    text: str = "I am checking that."


class SilenceAvoidancePolicy(VoiceRuntimeModel):
    max_silence_ms: int = 2500


class ContextualFillerSelection(VoiceRuntimeModel):
    intent_kind: str
    selected_text: str


def select_early_speech(trigger: EarlySpeechTrigger, *, policy: EarlySpeechPolicy) -> EarlySpeechResult:
    if not policy.enabled or trigger.elapsed_ms < policy.min_elapsed_ms:
        return EarlySpeechResult(should_speak=False, reason_code="early_speech.disabled_or_too_soon")
    if trigger.previous_filler_elapsed_ms is not None and trigger.previous_filler_elapsed_ms < policy.min_interval_ms:
        return EarlySpeechResult(should_speak=False, reason_code="early_speech.rate_limited")
    text = {
        "web_search": "I am searching for the latest information.",
        "tool": "I am checking that.",
        "memory": "Give me a moment, this needs a careful answer.",
        "browser": "I am checking that.",
    }.get(trigger.intent_kind, "Give me a moment, this needs a careful answer.")
    event = EarlySpeechEvent(text=text, intent_kind=trigger.intent_kind)
    return EarlySpeechResult(should_speak=True, text=text, event=event, reason_code="early_speech.selected")
