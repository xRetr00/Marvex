from __future__ import annotations

from typing import Any

from packages.voice_runtime.assets import STTModelRegistry, TTSVoiceRegistry, VoiceDownloadRequest, VoiceTestRequest, VoiceTestResult, WakeWordModelRegistry
from packages.voice_runtime.base import safe_mapping
from packages.voice_runtime.config import VoiceRuntimeConfig
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
