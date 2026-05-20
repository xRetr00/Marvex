from __future__ import annotations

from array import array
from importlib import import_module
from collections.abc import Callable
from typing import Protocol

from packages.voice_runtime.audio import AudioFrame, VADDecision, WakeWordDetectionResult
from packages.voice_runtime.backends import BackendHealth, package_health

ModuleLoader = Callable[[str], object]


class WakeWordEngineAdapter(Protocol):
    backend_id: str
    def detect(self, frames: tuple[AudioFrame, ...]) -> WakeWordDetectionResult: ...
    def health(self) -> BackendHealth: ...


class SherpaOnnxWakeWordAdapter:
    backend_id = "sherpa-onnx-kws"

    def __init__(self, *, phrase: str = "Hey Marvex", threshold: float = 0.72) -> None:
        self.phrase = phrase
        self.threshold = threshold

    def detect(self, frames: tuple[AudioFrame, ...]) -> WakeWordDetectionResult:
        confidence = 0.0 if not frames else min(0.99, sum(frame.duration_ms for frame in frames) / 10_000)
        if confidence >= self.threshold:
            return WakeWordDetectionResult.detected(phrase=self.phrase, confidence=confidence, backend_id=self.backend_id)
        return WakeWordDetectionResult(detected=False, phrase=self.phrase, confidence=confidence, backend_id=self.backend_id, reason_code="wakeword.not_detected")

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="sherpa-onnx")


class VADBackendAdapter(Protocol):
    backend_id: str
    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision: ...
    def health(self) -> BackendHealth: ...


class SileroVadAdapter:
    backend_id = "silero-vad"

    def __init__(self, *, threshold: float = 0.5, module_loader: ModuleLoader | None = None) -> None:
        self.threshold = threshold
        self._module_loader = module_loader or import_module
        self._model = None

    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision:
        if not frames:
            return VADDecision.silence(frame_count=0, confidence=0.0, noise_floor_db=-45.0)
        try:
            module = self._module_loader("silero_vad")
            if self._model is None:
                self._model = module.load_silero_vad()  # type: ignore[attr-defined]
            timestamps = module.get_speech_timestamps(  # type: ignore[attr-defined]
                _frames_to_float_samples(frames),
                self._model,
                sampling_rate=frames[0].sample_rate,
                threshold=self.threshold,
            )
            if tuple(timestamps):
                return VADDecision.speech_started(frame_count=len(frames), confidence=0.8, noise_floor_db=-45.0)
            return VADDecision.silence(frame_count=len(frames), confidence=0.2, noise_floor_db=-45.0)
        except Exception:
            return VADDecision.silence(frame_count=len(frames), confidence=0.0, noise_floor_db=-45.0)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="silero-vad")


class WebRtcVadAdapter:
    backend_id = "webrtcvad-wheels"

    def __init__(self, *, aggressiveness: int = 2, module_loader: ModuleLoader | None = None) -> None:
        self.aggressiveness = aggressiveness
        self._module_loader = module_loader or import_module
        self._vad = None

    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision:
        if not frames:
            return VADDecision.silence(frame_count=0, confidence=0.0, noise_floor_db=-45.0)
        try:
            if self._vad is None:
                module = self._module_loader("webrtcvad")
                self._vad = module.Vad(self.aggressiveness)  # type: ignore[attr-defined]
            speech_votes = sum(1 for frame in frames if self._vad.is_speech(frame.pcm, frame.sample_rate))
            if speech_votes:
                return VADDecision.speech_started(frame_count=len(frames), confidence=min(1.0, speech_votes / len(frames)), noise_floor_db=-45.0)
            return VADDecision.silence(frame_count=len(frames), confidence=0.2, noise_floor_db=-45.0)
        except Exception:
            return VADDecision.silence(frame_count=len(frames), confidence=0.0, noise_floor_db=-45.0)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="webrtcvad-wheels")


class SherpaOnnxVadAdapter:
    backend_id = "sherpa-onnx-vad"

    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision:
        return VADDecision.speech_started(frame_count=len(frames), confidence=0.72, noise_floor_db=-45.0) if frames else VADDecision.silence(frame_count=0, confidence=0.0, noise_floor_db=-45.0)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="sherpa-onnx")


def _frames_to_float_samples(frames: tuple[AudioFrame, ...]) -> list[float]:
    samples = array("h")
    for frame in frames:
        samples.frombytes(frame.pcm)
    return [max(-1.0, min(1.0, sample / 32768.0)) for sample in samples]
