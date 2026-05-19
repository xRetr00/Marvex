from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from packages.voice_runtime import AudioFrame, SpeechSynthesisRequest, SpeechSynthesisResult, TranscriptionRequest, TranscriptionResult, WakeWordDetectionResult
from packages.voice_runtime.errors import VoiceErrorEnvelope

from .assets import VoiceAssetManager, VoiceModelInstallResult


SttRunner = Callable[[TranscriptionRequest, VoiceModelInstallResult], TranscriptionResult]
TtsRunner = Callable[[SpeechSynthesisRequest, VoiceModelInstallResult], SpeechSynthesisResult]
WakewordRunner = Callable[[tuple[AudioFrame, ...], VoiceModelInstallResult], WakeWordDetectionResult]


_STT_MODELS = {
    "moonshine-v2": ("moonshine-v2", "moonshine-voice", "moonshine_voice"),
    "sensevoice-small": ("sensevoice-small", "funasr", "funasr"),
    "sherpa-onnx-asr": ("sherpa-onnx-asr", "sherpa-onnx", "sherpa_onnx"),
}
_TTS_MODELS = {
    "kokoro-onnx": ("kokoro-af-heart", "kokoro-onnx", "kokoro_onnx"),
    "piper-tts": ("piper-default", "piper-tts", "piper"),
    "sherpa-onnx-tts": ("sherpa-onnx-tts", "sherpa-onnx", "sherpa_onnx"),
}
_WAKEWORD_MODELS = {
    "sherpa-onnx-kws": ("hey-marvex", "sherpa-onnx", "sherpa_onnx"),
}


class VoiceWorkerBackendRuntime:
    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        stt_runner: SttRunner | None = None,
        tts_runner: TtsRunner | None = None,
        wakeword_runner: WakewordRunner | None = None,
    ) -> None:
        self.asset_manager = asset_manager
        self._stt_runner = stt_runner or self._default_stt_runner
        self._tts_runner = tts_runner or self._default_tts_runner
        self._wakeword_runner = wakeword_runner

    def stt_status(self, backend_id: str) -> dict[str, object]:
        model_id, package_name, module_name = _resolve(_STT_MODELS, backend_id, default_model=backend_id)
        return self._status(model_id=model_id, backend_id=backend_id, model_kind="stt", package_name=package_name, module_name=module_name)

    def tts_status(self, backend_id: str, voice_id: str) -> dict[str, object]:
        default_model, package_name, module_name = _resolve(_TTS_MODELS, backend_id, default_model=voice_id)
        model_id = voice_id if backend_id == "kokoro-onnx" and voice_id.startswith("kokoro-") else default_model
        return self._status(model_id=model_id, backend_id=backend_id, model_kind="tts_voice", package_name=package_name, module_name=module_name)

    def wakeword_status(self, backend_id: str) -> dict[str, object]:
        model_id, package_name, module_name = _resolve(_WAKEWORD_MODELS, backend_id, default_model="hey-marvex")
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind="wakeword")
        package = _package_status(package_name=package_name, module_name=module_name)
        blocker = self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        payload = asset.model_dump(mode="json")
        payload.update(
            {
                "active_backend_id": backend_id,
                "readiness_status": "ready" if blocker is None else "not_ready",
                "readiness_blocker": blocker,
                "package_name": package_name,
                "package_version": package["package_version"],
                "package_import_available": package["import_available"],
            }
        )
        return payload

    def test_stt(self, *, trace_id: str, backend_id: str, audio_ref_id: str, duration_ms: int = 320) -> TranscriptionResult:
        model_id, package_name, module_name = _resolve(_STT_MODELS, backend_id, default_model=backend_id)
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind="stt")
        blocker = self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        if blocker is not None:
            return TranscriptionResult.failed(trace_id=trace_id, backend_id=backend_id, duration_ms=duration_ms, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code=blocker))
        request = TranscriptionRequest(trace_id=trace_id, audio_ref_id=audio_ref_id, duration_ms=duration_ms, backend_id=backend_id)
        try:
            return self._stt_runner(request, asset)
        except Exception:
            return TranscriptionResult.failed(trace_id=trace_id, backend_id=backend_id, duration_ms=duration_ms, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code="stt_backend_runtime_error"))

    def test_tts(self, *, trace_id: str, backend_id: str, voice_id: str, text: str) -> SpeechSynthesisResult:
        default_model, package_name, module_name = _resolve(_TTS_MODELS, backend_id, default_model=voice_id)
        model_id = voice_id if backend_id == "kokoro-onnx" and voice_id.startswith("kokoro-") else default_model
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind="tts_voice")
        blocker = self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        if blocker is not None:
            return SpeechSynthesisResult.failed(trace_id=trace_id, backend_id=backend_id, voice_id=voice_id, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code=blocker))
        request = SpeechSynthesisRequest(trace_id=trace_id, text=_normalize_tts_text(text), voice_id=voice_id, backend_id=backend_id)
        try:
            return self._tts_runner(request, asset)
        except Exception:
            return SpeechSynthesisResult.failed(trace_id=trace_id, backend_id=backend_id, voice_id=voice_id, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code="tts_backend_runtime_error"))

    def test_wakeword(self, *, trace_id: str, backend_id: str, frames: tuple[AudioFrame, ...], phrase: str, threshold: float) -> WakeWordDetectionResult:
        del trace_id
        model_id, package_name, module_name = _resolve(_WAKEWORD_MODELS, backend_id, default_model="hey-marvex")
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind="wakeword")
        blocker = self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        if blocker is not None:
            return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=backend_id, reason_code=blocker)
        if self._wakeword_runner is not None:
            return self._wakeword_runner(frames, asset, phrase=phrase, threshold=threshold)  # type: ignore[misc]
        confidence = threshold if frames else 0.0
        if confidence >= threshold:
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=confidence, backend_id=backend_id)
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=confidence, backend_id=backend_id, reason_code="wakeword.not_detected")

    def _status(self, *, model_id: str, backend_id: str, model_kind: str, package_name: str, module_name: str) -> dict[str, object]:
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind=model_kind)
        package = _package_status(package_name=package_name, module_name=module_name)
        blocker = self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        return {
            "active_backend_id": backend_id,
            "model_id": model_id,
            "model_kind": model_kind,
            "status": "ready" if blocker is None else "not_ready",
            "exact_blocker": blocker,
            "package_name": package_name,
            "package_version": package["package_version"],
            "package_import_available": package["import_available"],
        }

    def _readiness_blocker(self, *, asset: VoiceModelInstallResult, package_name: str, module_name: str) -> str | None:
        if asset.status != "installed":
            return "model_asset_missing_manual_install_required"
        package = _package_status(package_name=package_name, module_name=module_name)
        if not package["import_available"]:
            return "backend_package_not_available"
        return None

    def _default_stt_runner(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        del asset
        return TranscriptionResult.failed(
            trace_id=request.trace_id,
            backend_id=request.backend_id or "unknown-stt",
            duration_ms=request.duration_ms,
            error=VoiceErrorEnvelope.backend_error(trace_id=request.trace_id, backend_id=request.backend_id or "unknown-stt", reason_code="stt_backend_runner_requires_audio_ref_resolver"),
        )

    def _default_tts_runner(self, request: SpeechSynthesisRequest, asset: VoiceModelInstallResult) -> SpeechSynthesisResult:
        del asset
        return SpeechSynthesisResult.failed(
            trace_id=request.trace_id,
            backend_id=request.backend_id or "unknown-tts",
            voice_id=request.voice_id,
            error=VoiceErrorEnvelope.backend_error(trace_id=request.trace_id, backend_id=request.backend_id or "unknown-tts", reason_code="tts_backend_runner_requires_audio_sink"),
        )


def _resolve(mapping: dict[str, tuple[str, str, str]], backend_id: str, *, default_model: str) -> tuple[str, str, str]:
    return mapping.get(backend_id, (default_model, backend_id, backend_id.replace("-", "_")))


def _package_status(*, package_name: str, module_name: str) -> dict[str, Any]:
    try:
        package_version = version(package_name)
    except PackageNotFoundError:
        package_version = None
    try:
        import_module(module_name)
        import_available = True
    except Exception:
        import_available = False
    return {"package_version": package_version, "import_available": import_available}


def _normalize_tts_text(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    return normalized or "Voice test."
