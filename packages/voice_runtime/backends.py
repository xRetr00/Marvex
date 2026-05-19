from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Literal, Protocol

from pydantic import Field

from packages.voice_runtime.base import VoiceRuntimeModel, safe_mapping
from packages.voice_runtime.errors import VoiceErrorEnvelope


class TranscriptionRequest(VoiceRuntimeModel):
    trace_id: str = Field(..., min_length=1)
    audio_ref_id: str = Field(..., min_length=1)
    duration_ms: int = Field(default=0, ge=0)
    language_hint: str | None = None
    backend_id: str | None = None
    raw_audio_persisted: Literal[False] = False


class TranscriptionResult(VoiceRuntimeModel):
    trace_id: str
    status: Literal["succeeded", "failed"]
    text: str | None = None
    language: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    segments: tuple[dict[str, object], ...] = ()
    backend_id: str
    duration_ms: int = 0
    safe_error: VoiceErrorEnvelope | None = None
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def succeeded(cls, *, trace_id: str, text: str, backend_id: str, duration_ms: int, language: str | None = None, confidence: float | None = None, segments: tuple[dict[str, object], ...] = ()) -> "TranscriptionResult":
        return cls(trace_id=trace_id, status="succeeded", text=text, language=language, confidence=confidence, segments=segments, backend_id=backend_id, duration_ms=duration_ms)

    @classmethod
    def failed(cls, *, trace_id: str, backend_id: str, duration_ms: int, error: VoiceErrorEnvelope) -> "TranscriptionResult":
        return cls(trace_id=trace_id, status="failed", backend_id=backend_id, duration_ms=duration_ms, safe_error=error)

    def safe_projection(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        if self.status == "succeeded":
            payload["text_present"] = bool(self.text)
            payload.pop("text", None)
        if self.status == "failed":
            for key in ("raw_audio_persisted", "raw_transcript_persisted"):
                payload.pop(key, None)
            if isinstance(payload.get("safe_error"), dict):
                payload["safe_error"] = {key: value for key, value in payload["safe_error"].items() if not key.startswith("raw_")}
        return safe_mapping(payload)


class SpeechSynthesisRequest(VoiceRuntimeModel):
    trace_id: str
    text: str = Field(..., min_length=1, max_length=2000)
    voice_id: str
    backend_id: str | None = None
    raw_text_persisted: Literal[False] = False


class SpeechSynthesisResult(VoiceRuntimeModel):
    trace_id: str
    status: Literal["succeeded", "failed"]
    audio_ref: str | None = None
    backend_id: str
    voice_id: str
    format: str = "pcm_s16le"
    sample_rate: int = 24000
    duration_ms: int | None = None
    safe_error: VoiceErrorEnvelope | None = None
    raw_audio_persisted: Literal[False] = False

    @classmethod
    def succeeded(cls, *, trace_id: str, audio_ref: str, backend_id: str, voice_id: str, sample_rate: int = 24000, duration_ms: int | None = None) -> "SpeechSynthesisResult":
        return cls(trace_id=trace_id, status="succeeded", audio_ref=audio_ref, backend_id=backend_id, voice_id=voice_id, sample_rate=sample_rate, duration_ms=duration_ms)

    @classmethod
    def failed(cls, *, trace_id: str, backend_id: str, voice_id: str, error: VoiceErrorEnvelope) -> "SpeechSynthesisResult":
        return cls(trace_id=trace_id, status="failed", backend_id=backend_id, voice_id=voice_id, safe_error=error)

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


class VoicePlaybackRequest(VoiceRuntimeModel):
    trace_id: str
    audio_ref: str
    backend_id: str
    text: str | None = None
    raw_audio_persisted: Literal[False] = False


class VoicePlaybackResult(VoiceRuntimeModel):
    trace_id: str
    status: Literal["queued", "playing", "completed", "interrupted", "failed"]
    audio_ref: str | None = None
    backend_id: str | None = None
    text: str | None = None
    raw_audio_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("text", None)
        return safe_mapping(payload)


class BackendHealth(VoiceRuntimeModel):
    backend_id: str
    package_name: str
    package_version: str | None
    import_available: bool
    model_installed: bool = False
    exact_blocker: str | None = None


class SttBackend(Protocol):
    backend_id: str
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult: ...
    def health(self) -> BackendHealth: ...


class TtsBackend(Protocol):
    backend_id: str
    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult: ...
    def health(self) -> BackendHealth: ...


def package_health(*, backend_id: str, package_name: str, model_installed: bool = False) -> BackendHealth:
    try:
        package_version = version(package_name)
        return BackendHealth(backend_id=backend_id, package_name=package_name, package_version=package_version, import_available=True, model_installed=model_installed)
    except PackageNotFoundError:
        return BackendHealth(backend_id=backend_id, package_name=package_name, package_version=None, import_available=False, model_installed=False, exact_blocker=f"{package_name} is not installed")


class DeterministicSttAdapter:
    def __init__(self, backend_id: str, *, text: str) -> None:
        self.backend_id = backend_id
        self.text = text

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text=self.text, backend_id=self.backend_id, duration_ms=request.duration_ms, language="en", confidence=0.99, segments=({"start_ms": 0, "end_ms": request.duration_ms, "text_present": True},))

    def health(self) -> BackendHealth:
        return BackendHealth(backend_id=self.backend_id, package_name="deterministic", package_version="test", import_available=True, model_installed=True)


class DeterministicTtsAdapter:
    def __init__(self, backend_id: str) -> None:
        self.backend_id = backend_id

    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        return SpeechSynthesisResult.succeeded(trace_id=request.trace_id, audio_ref=f"memory://voice/generated/{request.trace_id}/{request.voice_id}", backend_id=self.backend_id, voice_id=request.voice_id, duration_ms=max(120, len(request.text) * 12))

    def health(self) -> BackendHealth:
        return BackendHealth(backend_id=self.backend_id, package_name="deterministic", package_version="test", import_available=True, model_installed=True)


class PackageBackedSttAdapter:
    def __init__(self, backend_id: str, package_name: str) -> None:
        self.backend_id = backend_id
        self.package_name = package_name

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        error = VoiceErrorEnvelope.backend_error(trace_id=request.trace_id, backend_id=self.backend_id, reason_code="model_not_installed_or_not_configured")
        return TranscriptionResult.failed(trace_id=request.trace_id, backend_id=self.backend_id, duration_ms=request.duration_ms, error=error)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name=self.package_name)


class PackageBackedTtsAdapter:
    def __init__(self, backend_id: str, package_name: str) -> None:
        self.backend_id = backend_id
        self.package_name = package_name

    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        error = VoiceErrorEnvelope.backend_error(trace_id=request.trace_id, backend_id=self.backend_id, reason_code="voice_not_installed_or_not_configured")
        return SpeechSynthesisResult.failed(trace_id=request.trace_id, backend_id=self.backend_id, voice_id=request.voice_id, error=error)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name=self.package_name)


class VoiceBackendRegistry:
    def __init__(self, *, stt_backends: tuple[SttBackend, ...], tts_backends: tuple[TtsBackend, ...], main_stt: str, fallback_stt: str, main_tts: str, fallback_tts: str) -> None:
        self.stt_backends = {backend.backend_id: backend for backend in stt_backends}
        self.tts_backends = {backend.backend_id: backend for backend in tts_backends}
        self.main_stt = main_stt
        self.fallback_stt = fallback_stt
        self.main_tts = main_tts
        self.fallback_tts = fallback_tts

    def select_stt(self, selector: str) -> SttBackend:
        backend_id = self.main_stt if selector == "main" else self.fallback_stt if selector == "fallback" else selector
        return self.stt_backends[backend_id]

    def select_tts(self, selector: str) -> TtsBackend:
        backend_id = self.main_tts if selector == "main" else self.fallback_tts if selector == "fallback" else selector
        return self.tts_backends[backend_id]

    def safe_projection(self) -> dict[str, object]:
        return {
            "main_stt_backend_id": self.main_stt,
            "fallback_stt_backend_id": self.fallback_stt,
            "main_tts_backend_id": self.main_tts,
            "fallback_tts_backend_id": self.fallback_tts,
            "stt_switchable": len(self.stt_backends) > 1,
            "tts_switchable": len(self.tts_backends) > 1,
            "backend_health": [backend.health().model_dump(mode="json") for backend in (*self.stt_backends.values(), *self.tts_backends.values())],
        }


def build_default_voice_backend_registry(*, stt_backends: tuple[SttBackend, ...] | None = None, tts_backends: tuple[TtsBackend, ...] | None = None) -> VoiceBackendRegistry:
    stt = stt_backends or (PackageBackedSttAdapter("moonshine-v2", "moonshine-voice"), PackageBackedSttAdapter("sensevoice-small", "funasr"), PackageBackedSttAdapter("sherpa-onnx-asr", "sherpa-onnx"))
    tts = tts_backends or (PackageBackedTtsAdapter("kokoro-onnx", "kokoro-onnx"), PackageBackedTtsAdapter("piper-tts", "piper-tts"), PackageBackedTtsAdapter("sherpa-onnx-tts", "sherpa-onnx"))
    return VoiceBackendRegistry(stt_backends=stt, tts_backends=tts, main_stt="moonshine-v2", fallback_stt="sensevoice-small", main_tts="kokoro-onnx", fallback_tts="piper-tts")
