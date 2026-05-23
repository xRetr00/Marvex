from __future__ import annotations

from array import array
from collections.abc import Callable, Iterable
from importlib import import_module
from pathlib import Path
from typing import Any

from packages.voice_runtime import AudioFrame, SpeechSynthesisRequest, SpeechSynthesisResult, TranscriptionRequest, TranscriptionResult, WakeWordDetectionResult
from packages.voice_runtime.errors import VoiceErrorEnvelope

from .assets import VoiceAssetManager, VoiceModelInstallResult


class MoonshineSttRunner:
    def __init__(self, *, asset_manager: VoiceAssetManager, audio_refs: Any, transcriber_factory: Callable[[str], Any] | None = None) -> None:
        self.asset_manager = asset_manager
        self.audio_refs = audio_refs
        self.transcriber_factory = transcriber_factory

    def __call__(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        frames = self.audio_refs.resolve(request.audio_ref_id)
        blocker = _stt_blocker(path=path, frames=frames)
        if blocker:
            return _stt_failed(request, asset.backend_id, blocker)
        try:
            factory = self.transcriber_factory or import_module("moonshine_voice.transcriber").Transcriber
            transcriber = factory(str(path))
            try:
                transcript = transcriber.transcribe_without_streaming(_frames_to_float_samples(frames), sample_rate=frames[0].sample_rate)
            finally:
                close = getattr(transcriber, "close", None)
                if callable(close):
                    close()
            text, segments = _transcript_text_and_segments(transcript)
            return TranscriptionResult.succeeded(trace_id=request.trace_id, text=text, backend_id=asset.backend_id, duration_ms=_duration_ms(frames, request.duration_ms), language=request.language_hint or "en", segments=segments)
        except Exception:
            return _stt_failed(request, asset.backend_id, "moonshine_stt_runtime_error")


class SenseVoiceSttRunner:
    def __init__(self, *, asset_manager: VoiceAssetManager, audio_refs: Any, automodel_factory: Callable[..., Any] | None = None) -> None:
        self.asset_manager = asset_manager
        self.audio_refs = audio_refs
        self.automodel_factory = automodel_factory

    def __call__(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        frames = self.audio_refs.resolve(request.audio_ref_id)
        blocker = _stt_blocker(path=path, frames=frames)
        if blocker:
            return _stt_failed(request, asset.backend_id, blocker)
        try:
            factory = self.automodel_factory or import_module("funasr").AutoModel
            model = factory(model=str(path), disable_update=True)
            output = model.generate(input=_frames_to_float_samples(frames), fs=frames[0].sample_rate, language=request.language_hint or "auto")
            text, segments = _funasr_text_and_segments(output)
            return TranscriptionResult.succeeded(trace_id=request.trace_id, text=text, backend_id=asset.backend_id, duration_ms=_duration_ms(frames, request.duration_ms), language=request.language_hint, segments=segments)
        except Exception:
            return _stt_failed(request, asset.backend_id, "sensevoice_stt_runtime_error")


class KokoroOnnxTtsRunner:
    def __init__(self, *, asset_manager: VoiceAssetManager, generated_audio: Any, kokoro_factory: Callable[..., Any] | None = None) -> None:
        self.asset_manager = asset_manager
        self.generated_audio = generated_audio
        self.kokoro_factory = kokoro_factory

    def __call__(self, request: SpeechSynthesisRequest, asset: VoiceModelInstallResult) -> SpeechSynthesisResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        if path is None:
            return _tts_failed(request, asset.backend_id, "model_asset_path_not_registered")
        model_path = _first_existing(path, ("model.onnx", "kokoro.onnx")) if path.is_dir() else path
        voices_path = _first_matching(path, ("voices.npy", "*.npy", "voices.bin", "voices.json", "voice.bin")) if path.is_dir() else None
        if model_path is None or voices_path is None:
            return _tts_failed(request, asset.backend_id, "kokoro_model_or_voice_file_missing")
        try:
            factory = self.kokoro_factory or import_module("kokoro_onnx").Kokoro
            kokoro = factory(str(model_path), str(voices_path))
            try:
                samples, sample_rate = kokoro.create(_normalize_text(request.text), voice=request.voice_id)
            except TypeError:
                samples, sample_rate = kokoro.create(_normalize_text(request.text), request.voice_id)
            pcm = _float_samples_to_pcm_bytes(samples)
            ref = self.generated_audio.remember_audio(trace_id=request.trace_id, voice_id=request.voice_id, pcm=pcm, sample_rate=int(sample_rate))
            return SpeechSynthesisResult.succeeded(trace_id=request.trace_id, audio_ref=ref.audio_ref_id, backend_id=asset.backend_id, voice_id=request.voice_id, sample_rate=int(sample_rate), duration_ms=_audio_duration_ms(byte_count=len(pcm), sample_rate=int(sample_rate)))
        except Exception:
            return _tts_failed(request, asset.backend_id, "kokoro_tts_runtime_error")


class PiperTtsRunner:
    def __init__(self, *, asset_manager: VoiceAssetManager, generated_audio: Any, voice_loader: Callable[..., Any] | None = None) -> None:
        self.asset_manager = asset_manager
        self.generated_audio = generated_audio
        self.voice_loader = voice_loader

    def __call__(self, request: SpeechSynthesisRequest, asset: VoiceModelInstallResult) -> SpeechSynthesisResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        if path is None:
            return _tts_failed(request, asset.backend_id, "model_asset_path_not_registered")
        model_path = _first_with_suffix(path, ".onnx") if path.is_dir() else path
        config_path = Path(str(model_path) + ".json") if model_path is not None else None
        if model_path is None or not model_path.exists():
            return _tts_failed(request, asset.backend_id, "piper_model_file_missing")
        if config_path is not None and not config_path.exists():
            config_path = None
        try:
            loader = self.voice_loader or import_module("piper").PiperVoice.load
            voice = loader(str(model_path), config_path=str(config_path) if config_path else None)
            chunks = tuple(voice.synthesize(_normalize_text(request.text)))
            pcm = b"".join(_chunk_bytes(chunk) for chunk in chunks)
            sample_rate = int(getattr(chunks[0], "sample_rate", 22050)) if chunks else 22050
            ref = self.generated_audio.remember_audio(trace_id=request.trace_id, voice_id=request.voice_id, pcm=pcm, sample_rate=sample_rate)
            return SpeechSynthesisResult.succeeded(trace_id=request.trace_id, audio_ref=ref.audio_ref_id, backend_id=asset.backend_id, voice_id=request.voice_id, sample_rate=sample_rate, duration_ms=_audio_duration_ms(byte_count=len(pcm), sample_rate=sample_rate))
        except Exception:
            return _tts_failed(request, asset.backend_id, "piper_tts_runtime_error")


class SherpaOnnxSttRunner:
    """Offline ASR via sherpa-onnx OfflineRecognizer.

    Uses ``OfflineRecognizer.from_pre_trained(model_dir)`` to auto-detect
    the model type from the installed model directory.  A custom
    ``recognizer_factory(model_dir: str) -> recognizer`` may be injected for
    tests without loading real ONNX weights.
    """

    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        audio_refs: Any,
        recognizer_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.asset_manager = asset_manager
        self.audio_refs = audio_refs
        self.recognizer_factory = recognizer_factory

    def __call__(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        frames = self.audio_refs.resolve(request.audio_ref_id)
        blocker = _stt_blocker(path=path, frames=frames)
        if blocker:
            return _stt_failed(request, asset.backend_id, blocker)
        try:
            if self.recognizer_factory is not None:
                recognizer = self.recognizer_factory(str(path))
            else:
                module = import_module("sherpa_onnx")
                recognizer = module.OfflineRecognizer.from_pre_trained(str(path))
            stream = recognizer.create_stream()
            stream.accept_waveform(frames[0].sample_rate, _frames_to_float_samples(frames))
            recognizer.decode_stream(stream)
            text = str(getattr(getattr(stream, "result", ""), "text", "")).strip()
            return TranscriptionResult.succeeded(
                trace_id=request.trace_id,
                text=text,
                backend_id=asset.backend_id,
                duration_ms=_duration_ms(frames, request.duration_ms),
                language=request.language_hint or "en",
                segments=({"text_present": bool(text)},),
            )
        except Exception:
            return _stt_failed(request, asset.backend_id, "sherpa_onnx_stt_runtime_error")


class SherpaOnnxTtsRunner:
    """Offline TTS via sherpa-onnx OfflineTts.

    Uses ``OfflineTts.from_pre_trained(model_dir)`` to auto-detect the TTS
    model type.  A custom ``tts_factory(model_dir: str) -> tts`` may be
    injected for tests without loading real ONNX weights.
    """

    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        generated_audio: Any,
        tts_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.asset_manager = asset_manager
        self.generated_audio = generated_audio
        self.tts_factory = tts_factory

    def __call__(self, request: SpeechSynthesisRequest, asset: VoiceModelInstallResult) -> SpeechSynthesisResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        if path is None:
            return _tts_failed(request, asset.backend_id, "model_asset_path_not_registered")
        try:
            if self.tts_factory is not None:
                tts = self.tts_factory(str(path))
            else:
                module = import_module("sherpa_onnx")
                tts = module.OfflineTts.from_pre_trained(str(path))
            audio = tts.generate(_normalize_text(request.text), sid=0, speed=1.0)
            samples = getattr(audio, "samples", [])
            sample_rate = int(getattr(audio, "sample_rate", 22_050))
            pcm = _float_samples_to_pcm_bytes(samples)
            ref = self.generated_audio.remember_audio(
                trace_id=request.trace_id,
                voice_id=request.voice_id,
                pcm=pcm,
                sample_rate=sample_rate,
            )
            return SpeechSynthesisResult.succeeded(
                trace_id=request.trace_id,
                audio_ref=ref.audio_ref_id,
                backend_id=asset.backend_id,
                voice_id=request.voice_id,
                sample_rate=sample_rate,
                duration_ms=_audio_duration_ms(byte_count=len(pcm), sample_rate=sample_rate),
            )
        except Exception:
            return _tts_failed(request, asset.backend_id, "sherpa_onnx_tts_runtime_error")


class SherpaOnnxKwsRunner:
    """Wakeword keyword spotting via sherpa-onnx KeywordSpotter.

    Uses ``KeywordSpotter.from_pre_trained(model_dir)`` to load the KWS model.
    A custom ``kws_factory(model_dir: str) -> kws`` may be injected for tests.
    """

    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        kws_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.asset_manager = asset_manager
        self.kws_factory = kws_factory

    def __call__(
        self,
        frames: tuple[AudioFrame, ...],
        asset: VoiceModelInstallResult,
        *,
        phrase: str,
        threshold: float,
    ) -> WakeWordDetectionResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        if not frames or path is None:
            return WakeWordDetectionResult(
                detected=False,
                phrase=phrase,
                confidence=0.0,
                backend_id=asset.backend_id,
                reason_code="sherpa_onnx_kws_not_ready",
            )
        try:
            if self.kws_factory is not None:
                kws = self.kws_factory(str(path))
            else:
                module = import_module("sherpa_onnx")
                files = _resolve_kws_files(path)
                if files is None:
                    return WakeWordDetectionResult(
                        detected=False,
                        phrase=phrase,
                        confidence=0.0,
                        backend_id=asset.backend_id,
                        reason_code="sherpa_onnx_kws_not_ready",
                    )
                encoder, decoder, joiner, tokens, keywords = files
                kws = module.KeywordSpotter(
                    tokens=str(tokens),
                    encoder=str(encoder),
                    decoder=str(decoder),
                    joiner=str(joiner),
                    keywords_file=str(keywords),
                    num_threads=1,
                    provider="cpu",
                )
            stream = kws.create_stream()
            stream.accept_waveform(frames[0].sample_rate, _frames_to_float_samples(frames))
            kws.decode_stream(stream)
            result = stream.result
            keyword = str(getattr(result, "keyword", "")).strip()
            detected = bool(keyword)
            confidence = float(getattr(result, "confidence", threshold if detected else 0.0))
            if detected:
                return WakeWordDetectionResult.detected(phrase=phrase, confidence=confidence, backend_id=asset.backend_id)
            return WakeWordDetectionResult(
                detected=False,
                phrase=phrase,
                confidence=confidence,
                backend_id=asset.backend_id,
                reason_code="wakeword.not_detected",
            )
        except Exception:
            return WakeWordDetectionResult(
                detected=False,
                phrase=phrase,
                confidence=0.0,
                backend_id=asset.backend_id,
                reason_code="sherpa_onnx_kws_runtime_error",
            )


class VoiceWorkerSttModelRunner:
    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        audio_refs: Any,
        transcriber_factory: Callable[[str], Any] | None = None,
        automodel_factory: Callable[..., Any] | None = None,
        sherpa_recognizer_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._runners = {
            "moonshine-v2": MoonshineSttRunner(asset_manager=asset_manager, audio_refs=audio_refs, transcriber_factory=transcriber_factory),
            "sensevoice-small": SenseVoiceSttRunner(asset_manager=asset_manager, audio_refs=audio_refs, automodel_factory=automodel_factory),
            "sherpa-onnx-asr": SherpaOnnxSttRunner(asset_manager=asset_manager, audio_refs=audio_refs, recognizer_factory=sherpa_recognizer_factory),
        }

    def __call__(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        runner = self._runners.get(asset.backend_id)
        if runner is None:
            return _stt_failed(request, asset.backend_id, "stt_backend_model_adapter_not_implemented")
        return runner(request, asset)


class VoiceWorkerTtsModelRunner:
    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        generated_audio: Any,
        kokoro_factory: Callable[..., Any] | None = None,
        voice_loader: Callable[..., Any] | None = None,
        sherpa_tts_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._runners = {
            "kokoro-onnx": KokoroOnnxTtsRunner(asset_manager=asset_manager, generated_audio=generated_audio, kokoro_factory=kokoro_factory),
            "piper-tts": PiperTtsRunner(asset_manager=asset_manager, generated_audio=generated_audio, voice_loader=voice_loader),
            "sherpa-onnx-tts": SherpaOnnxTtsRunner(asset_manager=asset_manager, generated_audio=generated_audio, tts_factory=sherpa_tts_factory),
        }

    def __call__(self, request: SpeechSynthesisRequest, asset: VoiceModelInstallResult) -> SpeechSynthesisResult:
        runner = self._runners.get(asset.backend_id)
        if runner is None:
            return _tts_failed(request, asset.backend_id, "tts_backend_model_adapter_not_implemented")
        return runner(request, asset)


def _stt_blocker(*, path: Path | None, frames: tuple[AudioFrame, ...]) -> str | None:
    if path is None:
        return "model_asset_path_not_registered"
    if not frames:
        return "stt_audio_ref_not_available"
    return None


def _stt_failed(request: TranscriptionRequest, backend_id: str, reason_code: str) -> TranscriptionResult:
    return TranscriptionResult.failed(trace_id=request.trace_id, backend_id=backend_id, duration_ms=request.duration_ms, error=VoiceErrorEnvelope.backend_error(trace_id=request.trace_id, backend_id=backend_id, reason_code=reason_code))


def _tts_failed(request: SpeechSynthesisRequest, backend_id: str, reason_code: str) -> SpeechSynthesisResult:
    return SpeechSynthesisResult.failed(trace_id=request.trace_id, backend_id=backend_id, voice_id=request.voice_id, error=VoiceErrorEnvelope.backend_error(trace_id=request.trace_id, backend_id=backend_id, reason_code=reason_code))


def _duration_ms(frames: tuple[AudioFrame, ...], fallback: int) -> int:
    return sum(frame.duration_ms for frame in frames) or fallback


def _frames_to_float_samples(frames: tuple[AudioFrame, ...]) -> list[float]:
    samples = array("h")
    for frame in frames:
        samples.frombytes(frame.pcm)
    return [max(-1.0, min(1.0, sample / 32768.0)) for sample in samples]


def _float_samples_to_pcm_bytes(samples: Iterable[Any]) -> bytes:
    try:
        import numpy as np

        return (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
    except Exception:
        pass
    if hasattr(samples, "astype"):
        typed = samples.astype("int16")
        if hasattr(typed, "tobytes"):
            return bytes(typed.tobytes())
    pcm = array("h")
    for sample in samples:
        value = max(-1.0, min(1.0, float(sample)))
        pcm.append(int(value * 32767))
    return pcm.tobytes()


def _transcript_text_and_segments(transcript: Any) -> tuple[str, tuple[dict[str, object], ...]]:
    lines = getattr(transcript, "lines", None) or []
    if lines:
        texts = [str(getattr(line, "text", "")).strip() for line in lines if str(getattr(line, "text", "")).strip()]
        segments = tuple(_line_segment(line) for line in lines)
        return " ".join(texts).strip(), segments
    text = str(getattr(transcript, "text", transcript)).strip()
    return text, ({"text_present": bool(text)},)


def _funasr_text_and_segments(output: Any) -> tuple[str, tuple[dict[str, object], ...]]:
    first = output[0] if isinstance(output, list) and output else output
    if isinstance(first, dict):
        text = str(first.get("text") or "").strip()
        timestamps = first.get("timestamps") or first.get("timestamp") or []
        segments = tuple({"start_ms": int(pair[0]), "end_ms": int(pair[1]), "text_present": bool(text)} for pair in timestamps if isinstance(pair, (list, tuple)) and len(pair) >= 2)
        return text, segments or ({"text_present": bool(text)},)
    text = str(first).strip()
    return text, ({"text_present": bool(text)},)


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip() or "Voice test."


def _first_existing(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _first_matching(root: Path, patterns: tuple[str, ...]) -> Path | None:
    for pattern in patterns:
        exact = root / pattern
        if "*" not in pattern and exact.exists():
            return exact
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[0]
    return None


def _first_with_suffix(root: Path, suffix: str) -> Path | None:
    for candidate in sorted(root.iterdir()):
        if candidate.suffix == suffix:
            return candidate
    return None


def _resolve_kws_files(root: Path) -> tuple[Path, Path, Path, Path, Path] | None:
    """Resolve the sherpa-onnx KWS model files under ``root`` (nesting-tolerant,
    int8 preferred): (encoder, decoder, joiner, tokens, keywords). Returns None
    if any required file is missing."""

    def pick(glob: str) -> Path | None:
        matches = sorted(root.rglob(glob))
        if not matches:
            return None
        int8 = [m for m in matches if "int8" in m.name]
        return (int8 or matches)[0]

    encoder = pick("*encoder*.onnx")
    decoder = pick("*decoder*.onnx")
    joiner = pick("*joiner*.onnx")
    tokens = next(iter(sorted(root.rglob("tokens.txt"))), None)
    keywords = next(iter(sorted(root.rglob("keywords.txt"))), None)
    if not all((encoder, decoder, joiner, tokens, keywords)):
        return None
    return encoder, decoder, joiner, tokens, keywords  # type: ignore[return-value]


def _chunk_bytes(chunk: Any) -> bytes:
    for attr in ("audio_int16_bytes", "audio", "data"):
        value = getattr(chunk, attr, None)
        if isinstance(value, bytes):
            return value
        if hasattr(value, "tobytes"):
            return value.tobytes()
    if isinstance(chunk, bytes):
        return chunk
    return b""


def _audio_duration_ms(*, byte_count: int, sample_rate: int) -> int:
    if sample_rate <= 0:
        return 0
    return int((byte_count / 2) / sample_rate * 1000)


def _line_segment(line: Any) -> dict[str, object]:
    text = str(getattr(line, "text", "")).strip()
    if hasattr(line, "start_time") or hasattr(line, "duration"):
        start_ms = int(float(getattr(line, "start_time", 0.0)) * 1000)
        end_ms = int((float(getattr(line, "start_time", 0.0)) + float(getattr(line, "duration", 0.0))) * 1000)
    else:
        start_ms = int(float(getattr(line, "start", 0.0)) * 1000)
        end_ms = int(float(getattr(line, "end", 0.0)) * 1000)
    return {"start_ms": start_ms, "end_ms": end_ms, "text_present": bool(text)}
