from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import Field

from packages.voice_runtime.backends import DeterministicSttAdapter, DeterministicTtsAdapter, SpeechSynthesisRequest, SpeechSynthesisResult, TranscriptionRequest, TranscriptionResult, VoiceBackendRegistry, VoicePlaybackResult, build_default_voice_backend_registry
from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping
from packages.voice_runtime.config import VoiceRuntimeConfig
from packages.voice_runtime.errors import VoiceErrorEnvelope
from packages.voice_runtime.streaming import BargeInDetector, ChunkPlaybackState, PlaybackInterruptResult, UserSpeechDuringPlaybackEvent


class VoicePolicyDecision(VoiceRuntimeModel):
    trace_id: str
    decision: Literal["allow", "clarify", "approval_required", "quarantine", "deny"]
    reason_code: str
    execution_started: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def allow(cls, *, trace_id: str, reason_code: str) -> "VoicePolicyDecision":
        return cls(trace_id=trace_id, decision="allow", reason_code=reason_code)

    @classmethod
    def clarify(cls, *, trace_id: str, reason_code: str) -> "VoicePolicyDecision":
        return cls(trace_id=trace_id, decision="clarify", reason_code=reason_code)

    @classmethod
    def require_approval(cls, *, trace_id: str, reason_code: str) -> "VoicePolicyDecision":
        return cls(trace_id=trace_id, decision="approval_required", reason_code=reason_code)

    @classmethod
    def quarantine(cls, *, trace_id: str, reason_code: str) -> "VoicePolicyDecision":
        return cls(trace_id=trace_id, decision="quarantine", reason_code=reason_code)


class VoiceClarificationPrompt(VoiceRuntimeModel):
    trace_id: str
    prompt_text: str = "What should I do next?"
    no_execution_on_ambiguous_do_it: Literal[True] = True
    raw_transcript_persisted: Literal[False] = False


class VoiceApprovalPrompt(VoiceRuntimeModel):
    trace_id: str
    prompt_text: str = "Do you want me to proceed with that action?"
    approval_state: Literal["pending", "accepted", "denied", "canceled"] = "pending"
    control_plane_compatible: Literal[True] = True
    execution_started: Literal[False] = False


class SafeVoiceProjection(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    status: str
    backend_ids: dict[str, str]
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False
    raw_provider_payload_persisted: Literal[False] = False


class VoiceTurnRequest(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    turn_id: str
    trigger: Literal["wakeword", "manual", "push_to_talk"]
    audio_ref_id: str
    user_speech_during_playback: bool = False
    raw_audio_persisted: Literal[False] = False

    @classmethod
    def manual(cls, *, trace_id: str, audio_ref_id: str, user_speech_during_playback: bool = False) -> "VoiceTurnRequest":
        return cls(trace_id=trace_id, turn_id=f"voice-turn-{trace_id}", trigger="manual", audio_ref_id=audio_ref_id, user_speech_during_playback=user_speech_during_playback)


class VoiceTurnResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    turn_id: str
    status: Literal["completed", "clarification_required", "approval_required", "quarantined", "failed"]
    transcription: TranscriptionResult
    policy_decision: VoicePolicyDecision
    speech: SpeechSynthesisResult | None = None
    playback: VoicePlaybackResult
    barge_in: PlaybackInterruptResult | None = None
    clarification_prompt: VoiceClarificationPrompt | None = None
    approval_prompt: VoiceApprovalPrompt | None = None
    error: VoiceErrorEnvelope | None = None
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False
    raw_provider_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return SafeVoiceProjection(
            trace_id=self.trace_id,
            status=self.status,
            backend_ids={
                "stt": self.transcription.backend_id,
                "tts": self.speech.backend_id if self.speech else "none",
            },
        ).model_dump(mode="json")


class VoiceRuntimeSummary(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    main_stt_backend_id: str
    fallback_stt_backend_id: str
    main_tts_backend_id: str
    fallback_tts_backend_id: str
    wakeword_enabled: bool
    no_raw_audio_persistence_by_default: bool
    no_transcript_persistence_by_default: bool
    voice_runtime_owns_policy: Literal[False] = False
    voice_runtime_owns_intent: Literal[False] = False
    voice_runtime_owns_tools: Literal[False] = False
    voice_runtime_owns_memory: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class VoiceRuntime:
    def __init__(self, *, config: VoiceRuntimeConfig | None = None, backends: VoiceBackendRegistry | None = None) -> None:
        self.config = config or VoiceRuntimeConfig.default()
        self.backends = backends or build_default_voice_backend_registry()

    @classmethod
    def with_deterministic_backends(cls, *, stt: DeterministicSttAdapter, tts: DeterministicTtsAdapter, config: VoiceRuntimeConfig | None = None) -> "VoiceRuntime":
        backends = build_default_voice_backend_registry(stt_backends=(stt, DeterministicSttAdapter("sensevoice-small", text=stt.text)), tts_backends=(tts, DeterministicTtsAdapter("piper-tts")))
        return cls(config=config, backends=backends)

    def run_voice_turn(self, request: VoiceTurnRequest, *, assistant_turn_runner: Callable[[str], Any], policy_decider: Callable[[str], VoicePolicyDecision]) -> VoiceTurnResult:
        stt = self.backends.select_stt("main")
        transcription = stt.transcribe(TranscriptionRequest(trace_id=request.trace_id, audio_ref_id=request.audio_ref_id, duration_ms=320))
        if transcription.status != "succeeded" and self.config.backend_fallback.stt_auto_fallback_allowed:
            fallback_stt = self.backends.select_stt("fallback")
            if fallback_stt.backend_id != stt.backend_id:
                transcription = fallback_stt.transcribe(TranscriptionRequest(trace_id=request.trace_id, audio_ref_id=request.audio_ref_id, duration_ms=320))
        if transcription.status != "succeeded" or transcription.text is None:
            decision = VoicePolicyDecision(trace_id=request.trace_id, decision="deny", reason_code="voice.stt.failed")
            return self._error_result(request, transcription, decision, transcription.safe_error)
        decision = policy_decider(transcription.text)
        if decision.decision == "quarantine":
            error = VoiceErrorEnvelope.policy_block(trace_id=request.trace_id, reason_code=decision.reason_code)
            return self._error_result(request, transcription, decision, error, status="quarantined")
        if decision.decision == "clarify":
            prompt = VoiceClarificationPrompt(trace_id=request.trace_id)
            playback = VoicePlaybackResult(trace_id=request.trace_id, status="queued", text=prompt.prompt_text, backend_id="voice_runtime")
            return VoiceTurnResult(trace_id=request.trace_id, turn_id=request.turn_id, status="clarification_required", transcription=transcription, policy_decision=decision, playback=playback, clarification_prompt=prompt)
        if decision.decision == "approval_required":
            prompt = VoiceApprovalPrompt(trace_id=request.trace_id)
            playback = VoicePlaybackResult(trace_id=request.trace_id, status="queued", text=prompt.prompt_text, backend_id="voice_runtime")
            return VoiceTurnResult(trace_id=request.trace_id, turn_id=request.turn_id, status="approval_required", transcription=transcription, policy_decision=decision, playback=playback, approval_prompt=prompt)
        assistant_result = assistant_turn_runner(transcription.text)
        response_text = _assistant_text(assistant_result)
        tts = self.backends.select_tts("main")
        speech = tts.synthesize(SpeechSynthesisRequest(trace_id=request.trace_id, text=response_text, voice_id=self.config.personality.active_voice_id))
        if speech.status != "succeeded" and self.config.backend_fallback.tts_auto_fallback_allowed:
            fallback_tts = self.backends.select_tts("fallback")
            if fallback_tts.backend_id != tts.backend_id:
                speech = fallback_tts.synthesize(SpeechSynthesisRequest(trace_id=request.trace_id, text=response_text, voice_id=self.config.personality.active_voice_id))
        if speech.status != "succeeded":
            return self._error_result(request, transcription, decision, speech.safe_error)
        playback_status: Literal["queued", "interrupted"] = "queued"
        barge_in = None
        if request.user_speech_during_playback:
            barge_in = BargeInDetector(self.config.barge_in).evaluate(UserSpeechDuringPlaybackEvent(trace_id=request.trace_id, confidence=0.9, playback_chunk_id="spoken-0"), ChunkPlaybackState.playing(chunk_id="spoken-0", backend_id=speech.backend_id))
            playback_status = "interrupted" if barge_in.interrupted else "queued"
        playback = VoicePlaybackResult(trace_id=request.trace_id, status=playback_status, audio_ref=speech.audio_ref, backend_id=speech.backend_id, text=response_text)
        return VoiceTurnResult(trace_id=request.trace_id, turn_id=request.turn_id, status="completed", transcription=transcription, policy_decision=decision, speech=speech, playback=playback, barge_in=barge_in)

    def _error_result(self, request: VoiceTurnRequest, transcription: TranscriptionResult, decision: VoicePolicyDecision, error: VoiceErrorEnvelope | None, *, status: Literal["failed", "quarantined"] = "failed") -> VoiceTurnResult:
        playback = VoicePlaybackResult(trace_id=request.trace_id, status="failed", backend_id="voice_runtime")
        return VoiceTurnResult(trace_id=request.trace_id, turn_id=request.turn_id, status=status, transcription=transcription, policy_decision=decision, playback=playback, error=error)

    def summary(self) -> VoiceRuntimeSummary:
        projection = self.backends.safe_projection()
        return VoiceRuntimeSummary(
            main_stt_backend_id=str(projection["main_stt_backend_id"]),
            fallback_stt_backend_id=str(projection["fallback_stt_backend_id"]),
            main_tts_backend_id=str(projection["main_tts_backend_id"]),
            fallback_tts_backend_id=str(projection["fallback_tts_backend_id"]),
            wakeword_enabled=self.config.wakeword.always_listening_enabled,
            no_raw_audio_persistence_by_default=not self.config.audio_retention.raw_audio_persistence_allowed,
            no_transcript_persistence_by_default=not self.config.audio_retention.transcript_persistence_allowed,
        )

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping({"summary": self.summary(), "settings": self.config.safe_projection(), "backends": self.backends.safe_projection()})


def _assistant_text(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("text") or result.get("message") or "I can continue.")
    final_response = getattr(result, "assistant_final_response", None)
    final_text = getattr(final_response, "text", None)
    if final_text:
        return str(final_text)
    return str(getattr(result, "text", "I can continue."))
