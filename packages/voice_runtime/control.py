from __future__ import annotations

from typing import Any

from packages.voice_runtime.assets import STTModelRegistry, TTSVoiceRegistry, VoiceDownloadRequest, VoiceTestRequest, VoiceTestResult, WakeWordModelRegistry
from packages.voice_runtime.base import safe_mapping
from packages.voice_runtime.config import VoicePersonalityProfile, VoiceRuntimeConfig
from packages.voice_runtime.turn import VoiceRuntime


class VoiceControlPlaneFacade:
    def __init__(self, runtime: VoiceRuntime | None = None) -> None:
        self.runtime = runtime or VoiceRuntime()
        self.stt_models = STTModelRegistry()
        self.tts_voices = TTSVoiceRegistry()
        self.wakeword_models = WakeWordModelRegistry()

    def status(self) -> dict[str, object]:
        return safe_mapping({
            "schema_version": "1",
            "summary": self.runtime.summary(),
            "settings": self.runtime.config.safe_projection(),
            "backends": self.runtime.backends.safe_projection(),
            "assets": {
                "stt_models": self.stt_models.safe_projection(),
                "tts_voices": self.tts_voices.safe_projection(),
                "wakeword_models": self.wakeword_models.safe_projection(),
            },
            "telemetry": self.telemetry_summary(),
            "raw_audio_persisted": False,
            "raw_transcript_persisted": False,
        })

    def select_stt(self, payload: dict[str, Any]) -> dict[str, object]:
        main = str(payload.get("main_backend_id") or self.runtime.backends.main_stt)
        fallback = str(payload.get("fallback_backend_id") or self.runtime.backends.fallback_stt)
        if main in self.runtime.backends.stt_backends:
            self.runtime.backends.main_stt = main
        if fallback in self.runtime.backends.stt_backends:
            self.runtime.backends.fallback_stt = fallback
        return {"schema_version": "1", "main_backend_id": self.runtime.backends.main_stt, "fallback_backend_id": self.runtime.backends.fallback_stt, "execution_started": False, "raw_audio_persisted": False}

    def select_tts(self, payload: dict[str, Any]) -> dict[str, object]:
        main = str(payload.get("main_backend_id") or self.runtime.backends.main_tts)
        fallback = str(payload.get("fallback_backend_id") or self.runtime.backends.fallback_tts)
        voice = str(payload.get("active_voice_id") or self.runtime.config.personality.active_voice_id)
        if main in self.runtime.backends.tts_backends:
            self.runtime.backends.main_tts = main
        if fallback in self.runtime.backends.tts_backends:
            self.runtime.backends.fallback_tts = fallback
        personality = self.runtime.config.personality.model_copy(update={"active_voice_id": voice})
        self.runtime.config = self.runtime.config.model_copy(update={"personality": personality})
        return {"schema_version": "1", "main_backend_id": self.runtime.backends.main_tts, "fallback_backend_id": self.runtime.backends.fallback_tts, "active_voice_id": voice, "execution_started": False, "raw_generated_audio_persisted": False}

    def update_wakeword(self, payload: dict[str, Any]) -> dict[str, object]:
        enabled = bool(payload.get("always_listening_enabled", self.runtime.config.wakeword.always_listening_enabled))
        wakeword = self.runtime.config.wakeword.model_copy(update={"always_listening_enabled": enabled})
        policy = self.runtime.config.wakeword_policy.model_copy(update={"always_listening_enabled": enabled})
        self.runtime.config = self.runtime.config.model_copy(update={"wakeword": wakeword, "wakeword_policy": policy})
        return {"schema_version": "1", "wakeword": wakeword.model_dump(mode="json"), "execution_started": False, "raw_audio_persisted": False}

    def update_vad(self, payload: dict[str, Any]) -> dict[str, object]:
        backend = self.runtime.config.vad.backend.model_copy(update={
            "aggressiveness": int(payload.get("aggressiveness", self.runtime.config.vad.backend.aggressiveness)),
        })
        vad = self.runtime.config.vad.model_copy(update={
            "backend": backend,
            "noisy_room_handling_enabled": bool(payload.get("noisy_room_handling_enabled", self.runtime.config.vad.noisy_room_handling_enabled)),
        })
        self.runtime.config = self.runtime.config.model_copy(update={"vad": vad})
        return {"schema_version": "1", "vad": vad.model_dump(mode="json"), "execution_started": False, "raw_audio_persisted": False}

    def update_barge_in(self, payload: dict[str, Any]) -> dict[str, object]:
        barge_in = self.runtime.config.barge_in.model_copy(update={
            "enabled": bool(payload.get("enabled", self.runtime.config.barge_in.enabled)),
            "cancel_queued_tts": bool(payload.get("cancel_queued_tts", self.runtime.config.barge_in.cancel_queued_tts)),
        })
        self.runtime.config = self.runtime.config.model_copy(update={"barge_in": barge_in})
        return {"schema_version": "1", "barge_in": barge_in.model_dump(mode="json"), "execution_started": False, "queued_chunks_canceled": 0}

    def update_early_speech(self, payload: dict[str, Any]) -> dict[str, object]:
        early_speech = self.runtime.config.early_speech.model_copy(update={
            "enabled": bool(payload.get("enabled", self.runtime.config.early_speech.enabled)),
            "min_interval_ms": int(payload.get("min_interval_ms", self.runtime.config.early_speech.min_interval_ms)),
        })
        self.runtime.config = self.runtime.config.model_copy(update={"early_speech": early_speech})
        return {"schema_version": "1", "early_speech": early_speech.model_dump(mode="json"), "execution_started": False, "claims_facts_without_evidence": False}

    def update_personality(self, payload: dict[str, Any]) -> dict[str, object]:
        allowed = {key: value for key, value in payload.items() if key in {"profile_id", "filler_frequency", "confirmation_style", "sensitive_content_policy", "active_voice_id", "auto_speak_enabled", "speak_confirmations"}}
        personality = VoicePersonalityProfile.model_validate({**self.runtime.config.personality.model_dump(mode="json"), **allowed})
        self.runtime.config = self.runtime.config.model_copy(update={"personality": personality})
        return {"schema_version": "1", "personality": personality.safe_projection(), "execution_started": False, "raw_transcript_persisted": False}

    def update_retention(self, payload: dict[str, Any]) -> dict[str, object]:
        retention = self.runtime.config.audio_retention.model_copy(update={
            "raw_audio_persistence_allowed": bool(payload.get("raw_audio_persistence_allowed", self.runtime.config.audio_retention.raw_audio_persistence_allowed)),
            "transcript_persistence_allowed": bool(payload.get("transcript_persistence_allowed", self.runtime.config.audio_retention.transcript_persistence_allowed)),
            "generated_audio_persistence_allowed": bool(payload.get("generated_audio_persistence_allowed", self.runtime.config.audio_retention.generated_audio_persistence_allowed)),
        })
        self.runtime.config = self.runtime.config.model_copy(update={"audio_retention": retention})
        return {"schema_version": "1", "audio_retention": retention.model_dump(mode="json"), "execution_started": False}

    def download(self, payload: dict[str, Any]) -> dict[str, object]:
        request = VoiceDownloadRequest.model_validate(payload)
        registry = self.tts_voices if request.model_kind == "tts_voice" else self.wakeword_models if request.model_kind == "wakeword" else self.stt_models
        return registry.download(request).model_dump(mode="json")

    def remove(self, payload: dict[str, Any]) -> dict[str, object]:
        model_id = str(payload.get("model_id") or "")
        model_kind = str(payload.get("model_kind") or "")
        registry = self.tts_voices if model_kind == "tts_voice" else self.wakeword_models if model_kind == "wakeword" else self.stt_models
        return registry.remove(model_id).model_dump(mode="json")

    def test_stt(self, payload: dict[str, Any]) -> dict[str, object]:
        request = VoiceTestRequest.model_validate(payload)
        status = "passed" if request.backend_id in self.runtime.backends.stt_backends else "blocked"
        return VoiceTestResult.from_request(request, status=status).model_dump(mode="json")

    def test_tts(self, payload: dict[str, Any]) -> dict[str, object]:
        request = VoiceTestRequest.model_validate(payload)
        status = "passed" if request.backend_id in self.runtime.backends.tts_backends else "blocked"
        return VoiceTestResult.from_request(request, status=status).model_dump(mode="json")

    def update_config(self, config: VoiceRuntimeConfig) -> None:
        self.runtime.config = config

    def telemetry_summary(self) -> dict[str, object]:
        return {
            "wakeword_detections": 0,
            "vad_speech_segments": 0,
            "stt_requests": 0,
            "tts_requests": 0,
            "early_speech_events": 0,
            "barge_in_events": 0,
            "approval_prompts": 0,
            "voice_turn_completed": 0,
            "voice_turn_failed": 0,
            "durations_only": True,
            "raw_audio_persisted": False,
            "raw_transcript_persisted": False,
        }
