from __future__ import annotations

from typing import Protocol

from packages.voice_runtime.audio import AudioFrame, VADDecision, WakeWordDetectionResult
from packages.voice_runtime.backends import BackendHealth, package_health


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

    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision:
        return VADDecision.speech_started(frame_count=len(frames), confidence=0.8, noise_floor_db=-45.0) if frames else VADDecision.silence(frame_count=0, confidence=0.0, noise_floor_db=-45.0)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="silero-vad")


class WebRtcVadAdapter:
    backend_id = "webrtcvad-wheels"

    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision:
        return VADDecision.speech_started(frame_count=len(frames), confidence=0.7, noise_floor_db=-45.0) if frames else VADDecision.silence(frame_count=0, confidence=0.0, noise_floor_db=-45.0)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="webrtcvad-wheels")


class SherpaOnnxVadAdapter:
    backend_id = "sherpa-onnx-vad"

    def decide(self, frames: tuple[AudioFrame, ...]) -> VADDecision:
        return VADDecision.speech_started(frame_count=len(frames), confidence=0.72, noise_floor_db=-45.0) if frames else VADDecision.silence(frame_count=0, confidence=0.0, noise_floor_db=-45.0)

    def health(self) -> BackendHealth:
        return package_health(backend_id=self.backend_id, package_name="sherpa-onnx")
