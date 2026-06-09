from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal

from packages.voice_runtime import AudioFrame, SpeechSynthesisRequest, SpeechSynthesisResult, TranscriptionRequest, TranscriptionResult, WakeWordDetectionResult
from packages.voice_runtime.base import VoiceRuntimeModel
from packages.voice_runtime.errors import VoiceErrorEnvelope

from .assets import VoiceAssetManager, VoiceModelInstallResult
from .model_adapters import LanguageIdRunner, SherpaOnnxKwsRunner, VoiceWorkerSttModelRunner, VoiceWorkerTtsModelRunner


class VoiceWorkerAudioRef(VoiceRuntimeModel):
    audio_ref_id: str
    frame_count: int
    duration_ms: int
    byte_count: int
    sample_rate: int | None = None
    channel_count: int | None = None
    raw_audio_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class VoiceWorkerGeneratedAudioRef(VoiceRuntimeModel):
    audio_ref_id: str
    voice_id: str
    sample_rate: int
    byte_count: int
    raw_audio_persisted: Literal[False] = False
    raw_generated_audio_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class VoiceWorkerAudioRefStore:
    def __init__(self) -> None:
        self._frames: dict[str, tuple[AudioFrame, ...]] = {}
        self._refs: dict[str, VoiceWorkerAudioRef] = {}

    def remember_frames(self, *, trace_id: str, frames: tuple[AudioFrame, ...]) -> VoiceWorkerAudioRef:
        audio_ref_id = f"memory://voice/captured/{trace_id}"
        duration_ms = sum(frame.duration_ms for frame in frames)
        byte_count = sum(len(frame.pcm) for frame in frames)
        sample_rate = frames[0].sample_rate if frames else None
        channel_count = frames[0].channel_count if frames else None
        ref = VoiceWorkerAudioRef(audio_ref_id=audio_ref_id, frame_count=len(frames), duration_ms=duration_ms, byte_count=byte_count, sample_rate=sample_rate, channel_count=channel_count)
        self._frames[audio_ref_id] = frames
        self._refs[audio_ref_id] = ref
        return ref

    def resolve(self, audio_ref_id: str) -> tuple[AudioFrame, ...]:
        return self._frames.get(audio_ref_id, ())

    def safe_projection(self, audio_ref_id: str) -> dict[str, object]:
        ref = self._refs.get(audio_ref_id)
        if ref is None:
            return {"audio_ref_id": audio_ref_id, "frame_count": 0, "duration_ms": 0, "byte_count": 0, "raw_audio_persisted": False}
        return ref.safe_projection()


class VoiceWorkerGeneratedAudioSink:
    def __init__(self) -> None:
        self._audio: dict[str, bytes] = {}
        self._refs: dict[str, VoiceWorkerGeneratedAudioRef] = {}

    def remember_audio(self, *, trace_id: str, voice_id: str, pcm: bytes, sample_rate: int) -> VoiceWorkerGeneratedAudioRef:
        audio_ref_id = f"memory://voice/generated/{trace_id}/{voice_id}"
        ref = VoiceWorkerGeneratedAudioRef(audio_ref_id=audio_ref_id, voice_id=voice_id, sample_rate=sample_rate, byte_count=len(pcm))
        self._audio[audio_ref_id] = pcm
        self._refs[audio_ref_id] = ref
        return ref

    def resolve(self, audio_ref_id: str) -> bytes:
        return self._audio.get(audio_ref_id, b"")

    def safe_projection(self, audio_ref_id: str) -> dict[str, object]:
        ref = self._refs.get(audio_ref_id)
        if ref is None:
            return {"audio_ref_id": audio_ref_id, "byte_count": 0, "raw_audio_persisted": False, "raw_generated_audio_persisted": False}
        return ref.safe_projection()


SttRunner = Callable[[TranscriptionRequest, VoiceModelInstallResult], TranscriptionResult]
TtsRunner = Callable[[SpeechSynthesisRequest, VoiceModelInstallResult], SpeechSynthesisResult]
WakewordRunner = Callable[[tuple[AudioFrame, ...], VoiceModelInstallResult], WakeWordDetectionResult]
ModuleLoader = Callable[[str], Any]


_STT_MODELS = {
    "moonshine-v2": ("moonshine-v2", "moonshine-voice", "moonshine_voice"),
    "sensevoice-small": ("sensevoice-small", "funasr", "funasr"),
    "sherpa-onnx-asr": ("sherpa-onnx-asr", "sherpa-onnx", "sherpa_onnx"),
}
_TTS_MODELS = {
    "supertonic-v2": ("supertonic-v2", "supertonic", "supertonic"),
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
        langid_runner: Any | None = None,
        audio_refs: VoiceWorkerAudioRefStore | None = None,
        generated_audio: VoiceWorkerGeneratedAudioSink | None = None,
        module_loader: ModuleLoader | None = None,
    ) -> None:
        self.asset_manager = asset_manager
        self.audio_refs = audio_refs or VoiceWorkerAudioRefStore()
        self.generated_audio = generated_audio or VoiceWorkerGeneratedAudioSink()
        self._module_loader = module_loader or import_module
        self._custom_wakeword_runner = wakeword_runner is not None
        self._custom_stt_runner = stt_runner is not None
        self._custom_tts_runner = tts_runner is not None
        self._stt_runner = stt_runner or VoiceWorkerSttModelRunner(
            asset_manager=self.asset_manager,
            audio_refs=self.audio_refs,
            transcriber_factory=lambda *args, **kwargs: self._module_loader("moonshine_voice.transcriber").Transcriber(*args, **kwargs),
            automodel_factory=lambda **kwargs: self._module_loader("funasr").AutoModel(**kwargs),
            sherpa_recognizer_factory=lambda model_dir: self._module_loader("sherpa_onnx").OfflineRecognizer.from_pre_trained(model_dir),
        )
        self._tts_runner = tts_runner or VoiceWorkerTtsModelRunner(
            asset_manager=self.asset_manager,
            generated_audio=self.generated_audio,
            supertonic_factory=lambda *args, **kwargs: self._module_loader("supertonic").TTS(*args, **kwargs),
            voice_loader=lambda *args, **kwargs: self._module_loader("piper").PiperVoice.load(*args, **kwargs),
            sherpa_tts_factory=lambda model_dir: self._module_loader("sherpa_onnx").OfflineTts.from_pre_trained(model_dir),
        )
        self._wakeword_runner: Any = wakeword_runner or SherpaOnnxKwsRunner(
            asset_manager=self.asset_manager,
        )
        # Optional spoken-language-ID validator (SpeechBrain). Used only to let
        # the English-only Moonshine path ignore non-English utterances.
        self._langid_runner: Any = langid_runner or LanguageIdRunner(asset_manager=self.asset_manager)

    def _wakeword_runner_for(self, backend_id: str) -> Any:
        return self._wakeword_runner

    def warm(self, *, stt_backend_id: str, tts_backend_id: str, voice_id: str, speed: float = 1.05, quality_steps: int = 8, language: str = "en") -> dict[str, str]:
        """Eagerly load active STT and TTS model objects (best-effort)."""

        outcome: dict[str, str] = {"stt": "skipped", "tts": "skipped"}
        try:
            sample_rate = 16_000
            duration_ms = 320
            # 320ms of 16-bit mono silence — enough for the model to load and
            # run a no-op transcription pass.
            silent_pcm = b"\x00\x00" * (sample_rate * duration_ms // 1000)
            frame = AudioFrame(
                frame_id="voice-warm-stt-frame-1",
                pcm=silent_pcm,
                sample_rate=sample_rate,
                duration_ms=duration_ms,
                channel_count=1,
            )
            ref = self.remember_audio_frames(trace_id="voice-warm-stt", frames=(frame,))
            result = self.test_stt(
                trace_id="voice-warm-stt",
                backend_id=stt_backend_id,
                audio_ref_id=ref.audio_ref_id,
                duration_ms=duration_ms,
            )
            outcome["stt"] = "ok" if getattr(result, "status", "") == "succeeded" else "failed"
        except Exception:
            outcome["stt"] = "error"
        try:
            result = self.test_tts(
                trace_id="voice-warm-tts",
                backend_id=tts_backend_id,
                voice_id=voice_id,
                text="Warm up.",
                speed=speed,
                quality_steps=quality_steps,
                language=language,
            )
            outcome["tts"] = "ok" if getattr(result, "status", "") == "succeeded" else "failed"
        except Exception:
            outcome["tts"] = "error"
        return outcome

    def remember_audio_frames(self, *, trace_id: str, frames: tuple[AudioFrame, ...]) -> VoiceWorkerAudioRef:
        return self.audio_refs.remember_frames(trace_id=trace_id, frames=frames)

    def remember_captured_frames(self, *, trace_id: str, frames: tuple[AudioFrame, ...]) -> str:
        return self.remember_audio_frames(trace_id=trace_id, frames=frames).audio_ref_id

    def stt_status(self, backend_id: str) -> dict[str, object]:
        model_id, package_name, module_name = _resolve(_STT_MODELS, backend_id, default_model=backend_id)
        return self._status(model_id=model_id, backend_id=backend_id, model_kind="stt", package_name=package_name, module_name=module_name, custom_runner_ready=self._custom_stt_runner)

    def tts_status(self, backend_id: str, voice_id: str) -> dict[str, object]:
        default_model, package_name, module_name = _resolve(_TTS_MODELS, backend_id, default_model=voice_id)
        return self._status(model_id=default_model, backend_id=backend_id, model_kind="tts_voice", package_name=package_name, module_name=module_name, custom_runner_ready=self._custom_tts_runner)

    def wakeword_status(self, backend_id: str) -> dict[str, object]:
        model_id, package_name, module_name = _resolve(_WAKEWORD_MODELS, backend_id, default_model="hey-marvex")
        asset = self._wakeword_asset(backend_id=backend_id, model_id=model_id)
        package = _package_status(package_name=package_name, module_name=module_name)
        blocker = self.wakeword_readiness_blocker(backend_id)
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

    def wakeword_readiness_blocker(self, backend_id: str) -> str | None:
        model_id, package_name, module_name = _resolve(_WAKEWORD_MODELS, backend_id, default_model="hey-marvex")
        asset = self._wakeword_asset(backend_id=backend_id, model_id=model_id)
        if self._custom_wakeword_runner and asset.status == "installed":
            return None
        return self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)

    def test_stt(self, *, trace_id: str, backend_id: str, audio_ref_id: str, duration_ms: int = 320) -> TranscriptionResult:
        model_id, package_name, module_name = _resolve(_STT_MODELS, backend_id, default_model=backend_id)
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind="stt")
        # A caller-injected stt_runner is trusted to do its own readiness
        # checks (tests and embedded harnesses use this path). Skip the
        # package-import gate only when the model asset itself is installed.
        blocker = (
            None
            if self._custom_stt_runner and asset.status == "installed"
            else self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        )
        if blocker is not None:
            return TranscriptionResult.failed(trace_id=trace_id, backend_id=backend_id, duration_ms=duration_ms, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code=blocker))
        request = TranscriptionRequest(trace_id=trace_id, audio_ref_id=audio_ref_id, duration_ms=duration_ms, backend_id=backend_id)
        try:
            return self._stt_runner(request, asset)
        except Exception:
            return TranscriptionResult.failed(trace_id=trace_id, backend_id=backend_id, duration_ms=duration_ms, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code="stt_backend_runtime_error"))

    def open_stt_stream(self, *, backend_id: str, trace_id: str) -> Any:
        """Open a live streaming STT session, or ``None`` for non-streaming backends.

        Streaming partials are a Moonshine-only feature; everything else (and any
        failure) returns ``None`` so the caller falls back to one-shot ``test_stt``.
        """

        if backend_id != "moonshine-v2":
            return None
        opener = getattr(self._stt_runner, "open_stream", None)
        if not callable(opener):
            return None
        try:
            return opener(backend_id=backend_id, trace_id=trace_id)
        except Exception:
            return None

    def detect_language(self, *, frames: tuple[AudioFrame, ...]) -> tuple[str, float] | None:
        """Classify the spoken language of a final utterance clip, or ``None``.

        Fail-open: returns ``None`` (no verdict) when the language-ID model is not
        installed or anything goes wrong, so a missing optional model never blocks
        a turn. A non-``None`` result is ``(language_code, confidence)``.
        """

        try:
            return self._langid_runner.detect(tuple(frames))
        except Exception:
            return None

    def test_tts(self, *, trace_id: str, backend_id: str, voice_id: str, text: str, speed: float = 1.05, quality_steps: int = 8, language: str = "en") -> SpeechSynthesisResult:
        default_model, package_name, module_name = _resolve(_TTS_MODELS, backend_id, default_model=voice_id)
        asset = self.asset_manager.required_status(model_id=default_model, backend_id=backend_id, model_kind="tts_voice")
        # A caller-injected tts_runner is trusted to do its own readiness checks
        # (tests / embedded harnesses), mirroring the stt/wakeword pattern.
        blocker = (
            None
            if self._custom_tts_runner and asset.status == "installed"
            else self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
        )
        if blocker is not None:
            return SpeechSynthesisResult.failed(trace_id=trace_id, backend_id=backend_id, voice_id=voice_id, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code=blocker))
        request = SpeechSynthesisRequest(
            trace_id=trace_id,
            text=_normalize_tts_text(text),
            voice_id=voice_id,
            backend_id=backend_id,
            speed=speed,
            quality_steps=quality_steps,
            language=language,
        )
        try:
            return self._tts_runner(request, asset)
        except Exception:
            return SpeechSynthesisResult.failed(trace_id=trace_id, backend_id=backend_id, voice_id=voice_id, error=VoiceErrorEnvelope.backend_error(trace_id=trace_id, backend_id=backend_id, reason_code="tts_backend_runtime_error"))

    def test_wakeword(self, *, trace_id: str, backend_id: str, frames: tuple[AudioFrame, ...], phrase: str, threshold: float) -> WakeWordDetectionResult:
        del trace_id
        model_id, package_name, module_name = _resolve(_WAKEWORD_MODELS, backend_id, default_model="hey-marvex")
        asset = self._wakeword_asset(backend_id=backend_id, model_id=model_id)
        blocker = self.wakeword_readiness_blocker(backend_id)
        if blocker is not None:
            return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=backend_id, reason_code=blocker)
        return self._wakeword_runner_for(backend_id)(frames, asset, phrase=phrase, threshold=threshold)  # type: ignore[misc]

    def probe_wakeword(self, *, backend_id: str, frames: tuple[AudioFrame, ...], phrase: str, threshold: float) -> tuple[bool, str]:
        """Batch-probe ``frames`` on a FRESH stream (diagnostic only). Returns
        (detected, keyword). No-op (False, "") when the runner has no batch
        probe (e.g. test fakes) or the model is not ready."""

        probe = getattr(self._wakeword_runner_for(backend_id), "batch_probe", None)
        if not callable(probe):
            return False, ""
        model_id, package_name, module_name = _resolve(_WAKEWORD_MODELS, backend_id, default_model="hey-marvex")
        asset = self._wakeword_asset(backend_id=backend_id, model_id=model_id)
        blocker = self.wakeword_readiness_blocker(backend_id)
        if blocker is not None:
            return False, ""
        try:
            return probe(frames, asset, phrase=phrase, threshold=threshold)
        except Exception:
            return False, ""

    def _wakeword_asset(self, *, backend_id: str, model_id: str) -> VoiceModelInstallResult:
        return self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind="wakeword")

    def _status(self, *, model_id: str, backend_id: str, model_kind: str, package_name: str, module_name: str, custom_runner_ready: bool = False) -> dict[str, object]:
        asset = self.asset_manager.required_status(model_id=model_id, backend_id=backend_id, model_kind=model_kind)
        package = _package_status(package_name=package_name, module_name=module_name)
        blocker = None if custom_runner_ready and asset.status == "installed" else self._readiness_blocker(asset=asset, package_name=package_name, module_name=module_name)
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
