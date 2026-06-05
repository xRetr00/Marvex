from __future__ import annotations

import hashlib
import tempfile
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
        self._transcriber_key: tuple[str, str] | None = None
        self._transcriber: Any | None = None

    def _resolve_transcriber(self, path: Path) -> Any:
        factory = self.transcriber_factory or import_module("moonshine_voice.transcriber").Transcriber
        model_arch = _moonshine_model_arch(path)
        # On Windows, moonshine-c-api builds the tokenizer path with a ``\\?\``
        # extended-length prefix and a ``/`` separator, which the Win32 file APIs
        # reject literally even when the file is on disk. Resolving +
        # str-converting to a plain absolute path with the prefix stripped lets
        # moonshine concatenate "/tokenizer.bin" without the broken interaction.
        import os as _os

        path_str = _os.path.abspath(str(path))
        if path_str.startswith("\\\\?\\"):
            path_str = path_str[4:]
        key = (path_str, str(model_arch or ""))
        if self._transcriber is None or self._transcriber_key != key:
            if self._transcriber is not None:
                close = getattr(self._transcriber, "close", None)
                if callable(close):
                    close()
            try:
                self._transcriber = factory(path_str, model_arch=model_arch) if model_arch is not None else factory(path_str)
            except TypeError:
                self._transcriber = factory(path_str)
            self._transcriber_key = key
        return self._transcriber

    def __call__(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        frames = self.audio_refs.resolve(request.audio_ref_id)
        blocker = _stt_blocker(path=path, frames=frames)
        if blocker:
            return _stt_failed(request, asset.backend_id, blocker)
        try:
            transcriber = self._resolve_transcriber(path)  # type: ignore[arg-type]
            transcript = transcriber.transcribe_without_streaming(_frames_to_float_samples(frames), sample_rate=frames[0].sample_rate)
            text, segments = _transcript_text_and_segments(transcript)
            return TranscriptionResult.succeeded(trace_id=request.trace_id, text=text, backend_id=asset.backend_id, duration_ms=_duration_ms(frames, request.duration_ms), language=request.language_hint or "en", segments=segments)
        except Exception as exc:
            detail = type(exc).__name__
            reason = f"moonshine_stt_runtime_error:{detail}"
            return _stt_failed(request, asset.backend_id, reason[:240])

    def open_stream(self, *, trace_id: str) -> "MoonshineStreamSession | None":
        """Open a live streaming session, or ``None`` if the model isn't ready."""

        path = self.asset_manager.resolve_installed_path("moonshine-v2")
        if path is None:
            return None
        try:
            transcriber = self._resolve_transcriber(path)
            stream = transcriber.create_stream()
            start = getattr(stream, "start", None)
            if callable(start):
                start()
            return MoonshineStreamSession(stream=stream, backend_id="moonshine-v2", trace_id=trace_id)
        except Exception:
            return None


class MoonshineStreamSession:
    """Incremental Moonshine transcription: feed frames, read partials, finish.

    Wraps a moonshine ``Stream`` (``add_audio`` / ``update_transcription``). Used
    by the capture loop to emit live partial transcripts while the user speaks,
    then a final on endpoint. Any error mid-stream is the caller's signal to fall
    back to the one-shot path.
    """

    def __init__(self, *, stream: Any, backend_id: str, trace_id: str) -> None:
        self._stream = stream
        self._backend_id = backend_id
        self._trace_id = trace_id
        self._frames: list[AudioFrame] = []
        self._last_text = ""

    def feed(self, frame: AudioFrame) -> str | None:
        """Add one frame; return the updated partial text if it changed, else None."""

        self._frames.append(frame)
        self._stream.add_audio(_frames_to_float_samples((frame,)), frame.sample_rate)
        text, _segments = _transcript_text_and_segments(self._stream.update_transcription())
        if text and text != self._last_text:
            self._last_text = text
            return text
        return None

    def finish(self) -> TranscriptionResult:
        try:
            text, segments = _transcript_text_and_segments(self._stream.update_transcription())
            text = text or self._last_text
        finally:
            for method in ("stop", "close"):
                fn = getattr(self._stream, method, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass
        return TranscriptionResult.succeeded(
            trace_id=self._trace_id,
            text=text,
            backend_id=self._backend_id,
            duration_ms=_duration_ms(tuple(self._frames), 0),
            language="en",
            segments=segments if text else (),
        )


class SenseVoiceSttRunner:
    def __init__(self, *, asset_manager: VoiceAssetManager, audio_refs: Any, automodel_factory: Callable[..., Any] | None = None) -> None:
        self.asset_manager = asset_manager
        self.audio_refs = audio_refs
        self.automodel_factory = automodel_factory
        self._model_key: str | None = None
        self._model: Any | None = None

    def __call__(self, request: TranscriptionRequest, asset: VoiceModelInstallResult) -> TranscriptionResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        frames = self.audio_refs.resolve(request.audio_ref_id)
        blocker = _stt_blocker(path=path, frames=frames)
        if blocker:
            return _stt_failed(request, asset.backend_id, blocker)
        try:
            factory = self.automodel_factory or import_module("funasr").AutoModel
            model_key = str(path)
            if self._model is None or self._model_key != model_key:
                self._model = factory(model=model_key, disable_update=True)
                self._model_key = model_key
            output = self._model.generate(input=_frames_to_float_samples(frames), fs=frames[0].sample_rate, language=request.language_hint or "auto")
            text, segments = _funasr_text_and_segments(output)
            return TranscriptionResult.succeeded(trace_id=request.trace_id, text=text, backend_id=asset.backend_id, duration_ms=_duration_ms(frames, request.duration_ms), language=request.language_hint, segments=segments)
        except Exception:
            return _stt_failed(request, asset.backend_id, "sensevoice_stt_runtime_error")


class LanguageIdRunner:
    """Spoken-language identification over a final utterance clip.

    Lightweight endpoint validator (SpeechBrain ECAPA / VoxLingua107) whose only
    job is to classify the language of the captured utterance, so the
    English-only Moonshine path can ignore non-English speech. Run ONCE at
    endpoint, never on live mic audio. Fail-open: a missing model, an import
    error, or any failure returns ``None`` so the turn is allowed through.
    """

    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        classifier_factory: "Callable[[str], Callable[[list[float], int], tuple[str, float]]] | None" = None,
    ) -> None:
        self.asset_manager = asset_manager
        self.classifier_factory = classifier_factory
        self._classify: "Callable[[list[float], int], tuple[str, float]] | None" = None
        self._key: str | None = None

    def detect(self, frames: tuple[AudioFrame, ...]) -> tuple[str, float] | None:
        path = self.asset_manager.resolve_installed_path("speechbrain-langid")
        if path is None or not frames:
            return None
        try:
            factory = self.classifier_factory or _default_langid_classifier
            key = str(path)
            if self._classify is None or self._key != key:
                self._classify = factory(key)
                self._key = key
            code, confidence = self._classify(_frames_to_float_samples(frames), frames[0].sample_rate)
            return str(code).strip().lower(), float(confidence)
        except Exception:
            return None


def _default_langid_classifier(model_dir: str) -> "Callable[[list[float], int], tuple[str, float]]":
    classifiers = import_module("speechbrain.inference.classifiers")
    torch = import_module("torch")
    model = classifiers.EncoderClassifier.from_hparams(source=model_dir, savedir=model_dir)

    def classify(samples: list[float], sample_rate: int) -> tuple[str, float]:
        del sample_rate  # ECAPA frontend resamples internally; clips are already 16k.
        signal = torch.tensor(samples, dtype=torch.float32).unsqueeze(0)
        out_prob, score, _index, text_lab = model.classify_batch(signal)
        label = str(text_lab[0]) if len(text_lab) else ""
        code = label.split(":")[0].strip().lower() or "und"
        try:
            confidence = float(out_prob.exp().max().item())
        except Exception:
            try:
                confidence = float(score[0])
            except Exception:
                confidence = 0.0
        return code, confidence

    return classify


class KokoroOnnxTtsRunner:
    def __init__(self, *, asset_manager: VoiceAssetManager, generated_audio: Any, kokoro_factory: Callable[..., Any] | None = None) -> None:
        self.asset_manager = asset_manager
        self.generated_audio = generated_audio
        self.kokoro_factory = kokoro_factory
        self._kokoro_key: tuple[str, str] | None = None
        self._kokoro: Any | None = None

    def __call__(self, request: SpeechSynthesisRequest, asset: VoiceModelInstallResult) -> SpeechSynthesisResult:
        path = self.asset_manager.resolve_installed_path(asset.model_id)
        if path is None:
            return _tts_failed(request, asset.backend_id, "model_asset_path_not_registered")
        model_path = _first_existing(path, ("model.onnx", "kokoro.onnx")) if path.is_dir() else path
        voices_root = path if path.is_dir() else path.parent
        voices_path = _first_matching(voices_root, ("voices-v1.0.bin", "voices.npy", "*.npy", "voices.bin", "*.bin", "voices.json", "voice.bin"))
        if model_path is None or voices_path is None:
            return _tts_failed(request, asset.backend_id, "kokoro_model_or_voice_file_missing")
        try:
            factory = self.kokoro_factory or import_module("kokoro_onnx").Kokoro
            key = (str(model_path), str(voices_path))
            if self._kokoro is None or self._kokoro_key != key:
                self._kokoro = factory(str(model_path), str(voices_path))
                self._kokoro_key = key
            try:
                samples, sample_rate = self._kokoro.create(_normalize_text(request.text), voice=request.voice_id)
            except TypeError:
                samples, sample_rate = self._kokoro.create(_normalize_text(request.text), request.voice_id)
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
        self._voice_key: tuple[str, str] | None = None
        self._voice: Any | None = None

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
            key = (str(model_path), str(config_path) if config_path else "")
            if self._voice is None or self._voice_key != key:
                self._voice = loader(str(model_path), config_path=str(config_path) if config_path else None)
                self._voice_key = key
            chunks = tuple(self._voice.synthesize(_normalize_text(request.text)))
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

    The spotter and its detection stream are long-lived: sherpa-onnx KWS is a
    streaming detector whose mel-feature extractor needs ~1 s of audio
    history. Creating a fresh KeywordSpotter and stream per tick (the previous
    behaviour) discarded that history every iteration and would crash with
    ``GetFrames: 0 + 45 > N`` when the local buffer was shorter than the
    feature window. We now hold one spotter + stream per (asset, phrase,
    threshold) tuple, append each tick's PCM, decode incrementally, and reset
    only the stream (not the spotter) after a positive detection.

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
        self._cached_kws: Any | None = None
        self._cached_kws_key: tuple[str, str, float] | None = None
        self._cached_stream: Any | None = None
        # One-time diagnostic about the loaded keyword config (what tokens the
        # spotter is actually looking for). The wake word can fail silently when
        # the installed keywords file does not encode "Hey Marvex" in the
        # model's tokens; this surfaces that without persisting raw audio.
        self.keyword_diagnostic: dict[str, Any] | None = None

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
            kws, stream = self._ensure_session(
                path=path,
                asset=asset,
                phrase=phrase,
                threshold=threshold,
            )
            if kws is None or stream is None:
                return WakeWordDetectionResult(
                    detected=False,
                    phrase=phrase,
                    confidence=0.0,
                    backend_id=asset.backend_id,
                    reason_code="sherpa_onnx_kws_not_ready",
                )
            stream.accept_waveform(frames[0].sample_rate, _frames_to_float_samples(frames))
            self._drive_decode(kws, stream)
            result = self._read_kws_result(kws, stream)
            keyword, confidence = _kws_keyword_and_confidence(result, threshold)
            detected = bool(keyword)
            if detected:
                # Reset only the stream so the spotter (and its loaded model
                # weights) survive across detections. A fresh stream avoids
                # immediate re-trigger on the same audio window.
                reset = getattr(kws, "reset_stream", None)
                if callable(reset):
                    try:
                        reset(stream)
                        self._cached_stream = stream
                    except Exception:
                        self._cached_stream = kws.create_stream()
                else:
                    self._cached_stream = kws.create_stream()
                return WakeWordDetectionResult.detected(phrase=phrase, confidence=confidence, backend_id=asset.backend_id)
            return WakeWordDetectionResult(
                detected=False,
                phrase=phrase,
                confidence=confidence,
                backend_id=asset.backend_id,
                reason_code="wakeword.not_detected",
            )
        except Exception as exc:
            # Drop the cached stream so the next tick can rebuild cleanly,
            # but keep the spotter so we don't pay the model-load cost again.
            # Surface the exception class+short message into reason_code so
            # the worker stderr is actually useful when triaging in the field.
            self._cached_stream = None
            cls_name = type(exc).__name__[:48]
            detail = str(exc)[:96].replace("\n", " ").replace("\r", " ").strip()
            reason = f"sherpa_onnx_kws_runtime_error:{cls_name}"
            if detail:
                reason = f"{reason}:{detail}"
            return WakeWordDetectionResult(
                detected=False,
                phrase=phrase,
                confidence=0.0,
                backend_id=asset.backend_id,
                reason_code=reason[:240],
            )

    def batch_probe(self, frames: tuple[AudioFrame, ...], asset: VoiceModelInstallResult, *, phrase: str, threshold: float) -> tuple[bool, str]:
        """Run detection over ``frames`` on a FRESH stream, independent of the
        live persistent one. Diagnostic only: if this detects audio that the
        live loop missed, the persistent-stream feed is the problem (not the
        model/keyword/audio). Fed in 0.3s sub-chunks, mirroring the working
        offline path."""

        path = self.asset_manager.resolve_installed_path(asset.model_id)
        if not frames or path is None:
            return False, ""
        try:
            kws, _live_stream = self._ensure_session(path=path, asset=asset, phrase=phrase, threshold=threshold)
            if kws is None:
                return False, ""
            stream = kws.create_stream()
            sample_rate = frames[0].sample_rate
            samples = _frames_to_float_samples(frames)
            chunk = max(1, int(sample_rate * 0.3))
            for start in range(0, len(samples), chunk):
                stream.accept_waveform(sample_rate, samples[start:start + chunk])
                self._drive_decode(kws, stream)
                keyword, _confidence = _kws_keyword_and_confidence(self._read_kws_result(kws, stream), threshold)
                if keyword:
                    return True, keyword
            return False, ""
        except Exception:
            return False, ""

    def _drive_decode(self, kws: Any, stream: Any) -> None:
        """Decode whatever the spotter has buffered.

        sherpa-onnx 1.13.2 KeywordSpotter on Windows can be inconsistent about
        whether ``is_ready`` is exposed AND whether driving it in a loop is
        the right pattern for a session that retains state across ticks. We
        try ``is_ready``-gated decoding first (the recommended streaming
        pattern); if that raises, we fall back to a single ``decode_stream``
        call (which the spotter handles gracefully when its buffer is short).
        """

        ready = getattr(kws, "is_ready", None)
        if callable(ready):
            try:
                guard = 0
                while ready(stream) and guard < 1024:
                    kws.decode_stream(stream)
                    guard += 1
                return
            except Exception:
                # Fall through to single-shot decode.
                pass
        kws.decode_stream(stream)

    def _read_kws_result(self, kws: Any, stream: Any) -> Any:
        """Read the keyword-spotting result for a stream.

        sherpa-onnx 1.13.2's ``OnlineStream`` does NOT expose a ``.result``
        attribute (that raises AttributeError, which is exactly what halted
        the supervisor in the field). The real API is
        ``KeywordSpotter.get_result(stream)`` which returns the detected
        keyword string (empty when nothing matched). Test fakes use
        ``stream.result`` with a ``.keyword`` attribute, so we prefer
        ``get_result`` and fall back to the attribute for fakes.
        """

        get_result = getattr(kws, "get_result", None)
        if callable(get_result):
            return get_result(stream)
        return getattr(stream, "result", None)

    def _ensure_session(
        self,
        *,
        path: Path,
        asset: VoiceModelInstallResult,
        phrase: str,
        threshold: float,
    ) -> tuple[Any | None, Any | None]:
        key = (str(path), phrase, float(threshold))
        if self._cached_kws is None or self._cached_kws_key != key:
            self._cached_stream = None
            if self.kws_factory is not None:
                self._cached_kws = self.kws_factory(str(path))
            else:
                module = import_module("sherpa_onnx")
                files = _resolve_kws_files(path)
                if files is None:
                    self._cached_kws = None
                    self._cached_kws_key = None
                    return None, None
                encoder, decoder, joiner, tokens, keywords = files
                raw_keywords_preview = _safe_keywords_preview(keywords)
                # Prefer generating the keywords file from the configured phrase
                # using the model's own bpe.model, so the tokens always match what
                # the model expects (independent of whatever keywords.txt shipped).
                # Fall back to normalising the shipped file when bpe.model or
                # sentencepiece is unavailable.
                source = "generated_from_phrase"
                generated = _generate_kws_keywords_file(tokens=tokens, model_root=path, phrase=phrase)
                if generated is None:
                    source = "normalized_shipped"
                    generated = _normalized_kws_keywords_file(tokens=tokens, keywords=keywords)
                keywords = generated
                if keywords is None:
                    self.keyword_diagnostic = {
                        "phrase": phrase,
                        "threshold": float(threshold),
                        "keywords_file_loaded": False,
                        "reason": "keyword_tokens_not_in_model_vocabulary",
                        "raw_keywords_preview": raw_keywords_preview,
                    }
                    self._cached_kws = None
                    self._cached_kws_key = None
                    return None, None
                self.keyword_diagnostic = {
                    "phrase": phrase,
                    "threshold": float(threshold),
                    "keywords_file_loaded": True,
                    "keywords_source": source,
                    "keywords_preview": _safe_keywords_preview(keywords),
                    # Identify the actual model files loaded, so a stale/wrong
                    # cached encoder (the "cached voice assets" failure mode) is
                    # visible in the build logs.
                    "encoder_file": f"{encoder.name}:{_safe_file_size(encoder)}",
                    "decoder_file": f"{decoder.name}:{_safe_file_size(decoder)}",
                    "joiner_file": f"{joiner.name}:{_safe_file_size(joiner)}",
                }
                self._cached_kws = module.KeywordSpotter(
                    tokens=str(tokens),
                    encoder=str(encoder),
                    decoder=str(decoder),
                    joiner=str(joiner),
                    keywords_file=str(keywords),
                    num_threads=1,
                    keywords_threshold=threshold,
                    provider="cpu",
                )
            self._cached_kws_key = key
        if self._cached_stream is None and self._cached_kws is not None:
            self._cached_stream = self._cached_kws.create_stream()
        return self._cached_kws, self._cached_stream


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

    def open_stream(self, *, backend_id: str, trace_id: str) -> Any:
        runner = self._runners.get(backend_id)
        opener = getattr(runner, "open_stream", None)
        if not callable(opener):
            return None
        return opener(trace_id=trace_id)


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


def _moonshine_model_arch(path: Path | None) -> Any | None:
    if path is None or not path.is_dir():
        return None
    try:
        model_arch = import_module("moonshine_voice.moonshine_api").ModelArch
    except Exception:
        return None
    config = path / "streaming_config.json"
    if config.exists():
        # Identify the streaming arch from the model DIMENSIONS, not the dir
        # name. The asset installs as "moonshine-v2", so name matching returned
        # None -> Transcriber loaded a mismatched default layout -> "Required
        # tokenizer file does not exist". Dims per the Moonshine v2 paper:
        # Tiny enc=320/6L, Small enc=620/10L, Medium enc=768/14L.
        encoder_dim = 0
        depth = 0
        try:
            import json as _json

            dims = _json.loads(config.read_text(encoding="utf-8"))
            encoder_dim = int(dims.get("encoder_dim", 0) or 0)
            depth = int(dims.get("depth", 0) or 0)
        except Exception:
            pass
        name = path.name.lower()
        if encoder_dim >= 768 or depth >= 14 or "medium" in name:
            return model_arch.MEDIUM_STREAMING
        if encoder_dim >= 620 or depth >= 10 or "small" in name:
            return model_arch.SMALL_STREAMING
        return model_arch.TINY_STREAMING
    if (path / "encoder_model.ort").exists() and "tiny" in path.name.lower():
        return model_arch.TINY
    return None


def _kws_keyword_and_confidence(result: Any, threshold: float) -> tuple[str, float]:
    """Normalise a sherpa-onnx KWS result into (keyword, confidence).

    Handles all three shapes we encounter:
    * a plain ``str`` (sherpa-onnx 1.13.2 ``get_result`` returns the detected
      keyword text, or "" when nothing matched),
    * an object with ``.keyword`` / ``.confidence`` (test fakes and some
      sherpa-onnx builds expose a result object),
    * ``None`` (no result available).
    """

    if result is None:
        return "", 0.0
    if isinstance(result, str):
        keyword = result.strip()
        return keyword, (threshold if keyword else 0.0)
    keyword = str(getattr(result, "keyword", "")).strip()
    confidence = float(getattr(result, "confidence", threshold if keyword else 0.0))
    return keyword, confidence


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


# sherpa-onnx KWS per-keyword tuning. The keywords.txt line format is
# "<tokens> :BOOST #THRESHOLD @ALIAS" - ":" is the boosting score and "#" is the
# trigger threshold (NOT the other way round). Verified empirically against the
# gigaspeech KWS model on real "Hey Marvex" audio: ":2.0 #0.2" detects reliably;
# a high "#threshold" (e.g. the shipped ":1.5 #0.2" parsed wrong, or ":0.2 #2.0")
# never fires. Boost 2.0 + threshold 0.2 is the working pair.
_KWS_KEYWORD_BOOST = 2.0
# Trigger threshold (lower = easier to fire). Field logs showed real-voice
# "Hey Marvex" rarely cleared 0.2 even when loud and clear, so detection was
# near-zero across sessions. 0.1 trades a few possible false wakes for actually
# firing on the user's pronunciation; the fresh-stream batch probe is a second
# chance on top of this.
_KWS_KEYWORD_THRESHOLD = 0.1


# ARPAbet phonemes for coined wake words NOT in the model's en.phone lexicon
# (the zh-en KWS model is phoneme-based). "Marvex" is pronounced differently
# session to session (field logs: fires 4x one run, 0x the next), so we register
# SEVERAL plausible pronunciations as separate keyword lines to widen recall:
# stress on MAR vs MARV, EH vs IH vowel, AA vs AE.
_COINED_PHONEMES: dict[str, list[str]] = {
    "MARVEX": [
        "M AA1 R V EH1 K S",
        "M AA1 R V EH0 K S",
        "M AA1 R V IH0 K S",
        "M AA0 R V EH1 K S",
        "M AE1 R V EH1 K S",
        "M AA1 R V AH0 K S",
    ],
    "MARVECKS": ["M AA1 R V EH1 K S"],
    "MARVIX": ["M AA1 R V IH1 K S"],
}


def _wake_candidates(phrase: str) -> list[str]:
    base = " ".join(phrase.strip().upper().split())
    if not base:
        return []
    last_word = base.split()[-1]
    candidates = [base]
    for prefix in ("HI", "OK", "HELLO"):
        variant = f"{prefix} {last_word}"
        if variant not in candidates:
            candidates.append(variant)
    return candidates


def _bpe_keyword_pieces(model_root: Path, candidates: list[str], vocabulary: set[str]) -> list[tuple[str, list[str]]]:
    bpe = next(iter(sorted(model_root.rglob("bpe.model"))), None)
    if bpe is None:
        return []
    try:
        import sentencepiece as spm  # type: ignore[import-not-found]

        sp = spm.SentencePieceProcessor()
        sp.load(str(bpe))
    except Exception:
        return []
    out: list[tuple[str, list[str]]] = []
    for text in candidates:
        try:
            pieces = [str(piece) for piece in sp.encode(text, out_type=str)]
        except Exception:
            continue
        if pieces and all(piece in vocabulary for piece in pieces):
            out.append((text, pieces))
    return out


def _phoneme_keyword_pieces(model_root: Path, candidates: list[str], vocabulary: set[str]) -> list[tuple[str, list[str]]]:
    en_phone = next(iter(sorted(model_root.rglob("en.phone"))), None)
    if en_phone is None:
        return []
    lexicon: dict[str, str] = {}
    try:
        for line in en_phone.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                lexicon[parts[0].upper()] = " ".join(parts[1:])
    except OSError:
        return []
    import itertools

    out: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for text in candidates:
        # Per-word phone options: a coined word contributes several
        # pronunciations; lexicon words contribute one. The cross product yields
        # one keyword line per pronunciation (bounded), each with a unique alias.
        word_options: list[list[str]] = []
        ok = True
        for word in text.split():
            options = _COINED_PHONEMES.get(word)
            if options is None:
                lex = lexicon.get(word)
                options = [lex] if lex else []
            if not options:
                ok = False
                break
            word_options.append(list(options))
        if not ok:
            continue
        alias_base = "_".join(text.split())
        variant = 0
        for combo in list(itertools.product(*word_options))[:8]:
            phones: list[str] = []
            for spelled in combo:
                phones.extend(spelled.split())
            if not phones or any(p not in vocabulary for p in phones):
                continue
            key = " ".join(phones)
            if key in seen:
                continue
            seen.add(key)
            alias = alias_base if variant == 0 else f"{alias_base}_{variant}"
            out.append((alias, phones))
            variant += 1
    return out


def _generate_kws_keywords_file(*, tokens: Path, model_root: Path, phrase: str) -> Path | None:
    """Generate a keywords file from the wake phrase using the model's own
    tokenizer, so the keyword tokens always match what the model emits.

    Handles both KWS model families:
      * BPE (open-vocab, e.g. gigaspeech): sentencepiece-encode via bpe.model.
      * Phoneme (e.g. zh-en zipformer): map words to ARPAbet phones via the
        model's en.phone lexicon (plus _COINED_PHONEMES for "Marvex").
    Returns None when neither tokenizer is usable, so the caller falls back to
    normalising the shipped keywords file.
    """

    vocabulary = _load_token_vocabulary(tokens)
    if not vocabulary:
        return None
    candidates = _wake_candidates(phrase)
    if not candidates:
        return None
    pieces = _bpe_keyword_pieces(model_root, candidates, vocabulary) or _phoneme_keyword_pieces(
        model_root, candidates, vocabulary
    )
    if not pieces:
        return None
    lines = [
        " ".join(toks) + f" :{_KWS_KEYWORD_BOOST} #{_KWS_KEYWORD_THRESHOLD} @{'_'.join(text.split())}"
        for text, toks in pieces
    ]
    content = "\n".join(lines) + "\n"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    target = Path(tempfile.gettempdir()) / f"marvex-kws-generated-{digest}.txt"
    try:
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            target.write_text(content, encoding="utf-8")
    except OSError:
        return None
    return target


def _normalized_kws_keywords_file(*, tokens: Path, keywords: Path) -> Path | None:
    vocabulary = _load_token_vocabulary(tokens)
    if not vocabulary:
        return None
    try:
        original = keywords.read_text(encoding="utf-8")
    except OSError:
        return None
    normalized_lines: list[str] = []
    changed = False
    for line in original.splitlines():
        parts = line.strip().split()
        if not parts:
            normalized_lines.append("")
            continue
        alias_index = next((index for index, part in enumerate(parts) if part.startswith("@")), None)
        if alias_index is not None and alias_index < len(parts) - 1:
            alias = "_".join([parts[alias_index].lstrip("@"), *parts[alias_index + 1 :]])
            parts = [*parts[:alias_index], f"@{alias}"]
            changed = True
        keyword_tokens = [part for part in parts if not part.startswith(("#", ":", "@"))]
        if any(part not in vocabulary for part in keyword_tokens):
            return None
        # Force a usable boost + trigger threshold regardless of what shipped.
        # Format is ":BOOST #THRESHOLD".
        existing_boost = next((part for part in parts if part.startswith(":")), None)
        existing_threshold = next((part for part in parts if part.startswith("#")), None)
        alias_token = next((part for part in parts if part.startswith("@")), None)
        rebuilt = [*keyword_tokens, f":{_KWS_KEYWORD_BOOST}", f"#{_KWS_KEYWORD_THRESHOLD}"]
        if alias_token is not None:
            rebuilt.append(alias_token)
        if existing_boost != f":{_KWS_KEYWORD_BOOST}" or existing_threshold != f"#{_KWS_KEYWORD_THRESHOLD}":
            changed = True
        parts = rebuilt
        normalized_lines.append(" ".join(parts))
    normalized = "\n".join(normalized_lines).strip() + "\n"
    if not changed:
        return keywords
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    target = Path(tempfile.gettempdir()) / f"marvex-kws-keywords-{digest}.txt"
    try:
        if not target.exists() or target.read_text(encoding="utf-8") != normalized:
            target.write_text(normalized, encoding="utf-8")
    except OSError:
        return None
    return target


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return -1


def _safe_keywords_preview(keywords: Path) -> str:
    """First few keyword lines, bounded - so we can see the actual tokens the
    spotter is configured with (e.g. whether "Hey Marvex" is encoded as model
    tokens). Not raw audio; safe to log."""

    try:
        text = keywords.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:4])[:240]


def _load_token_vocabulary(tokens: Path) -> set[str]:
    try:
        lines = tokens.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    vocabulary: set[str] = set()
    for line in lines:
        parts = line.strip().split()
        if parts:
            vocabulary.add(parts[0])
    return vocabulary


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
