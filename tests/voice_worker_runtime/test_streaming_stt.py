"""Tests for Moonshine streaming partial transcripts and the capture integration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from packages.voice_runtime import AudioFrame, TranscriptionResult, WakeWordDetectionResult
from packages.voice_worker_runtime import (
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerBackendRuntime,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
)
from packages.voice_worker_runtime.continuous_capture import FakeContinuousCapture
from packages.voice_worker_runtime.model_adapters import MoonshineStreamSession
from packages.voice_worker_runtime.models import VoiceWorkerEventType


def _frame(tag: str, i: int) -> AudioFrame:
    return AudioFrame(frame_id=f"{tag}{i}", pcm=b"\x01\x00" * 160, sample_rate=16_000, channel_count=1, duration_ms=100)


class _FakeMoonshineStream:
    """Mimics a moonshine Stream: text grows as audio is fed."""

    def __init__(self, partials: list[str]) -> None:
        self._partials = partials
        self._fed = 0
        self.stopped = False
        self.closed = False

    def add_audio(self, _samples, _sample_rate) -> None:
        self._fed += 1

    def update_transcription(self, *_args, **_kwargs):
        index = min(self._fed, len(self._partials)) - 1
        text = self._partials[index] if index >= 0 else ""
        return SimpleNamespace(lines=[SimpleNamespace(text=text)] if text else [])

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


def test_stream_session_emits_growing_partials_then_final() -> None:
    stream = _FakeMoonshineStream(["what", "what time", "what time is it"])
    session = MoonshineStreamSession(stream=stream, backend_id="moonshine-v2", trace_id="t-1")

    seen = [session.feed(_frame("s", i)) for i in range(3)]
    assert seen == ["what", "what time", "what time is it"]
    # An extra frame with no new text yields no partial.
    assert session.feed(_frame("s", 3)) is None

    final = session.finish()
    assert final.status == "succeeded"
    assert final.text == "what time is it"
    assert stream.stopped and stream.closed


class _StreamingSttRunner:
    """Injectable STT runner that supports both streaming and one-shot fallback."""

    def __init__(self, partials: list[str], final_text: str) -> None:
        self.partials = partials
        self.final_text = final_text
        self.one_shot_calls = 0

    def __call__(self, request, asset) -> TranscriptionResult:  # one-shot fallback
        self.one_shot_calls += 1
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text=self.final_text, backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    def open_stream(self, *, backend_id, trace_id):
        return MoonshineStreamSession(stream=_FakeMoonshineStream(self.partials), backend_id=backend_id, trace_id=trace_id)


def _controller(tmp_path: Path, stt_runner, *, stt_backend="moonshine-v2"):
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex", explicit_user_triggered=True))
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True))

    def wakeword_runner(frames, asset, *, phrase, threshold):
        if any(f.frame_id.startswith("w") for f in frames):
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=asset.backend_id, reason_code="wakeword.not_detected")

    cfg = VoiceWorkerConfig.default()
    cfg = cfg.model_copy(update={"active_stt_backend_id": stt_backend, "wakeword": cfg.wakeword.model_copy(update={"enabled": True}), "vad": cfg.vad.model_copy(update={"silence_timeout_ms": 300, "tail_padding_ms": 100, "max_utterance_ms": 3000})})
    controller = VoiceWorkerController(
        config=cfg, asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner, stt_runner=stt_runner),
    )
    controller._vad_decider = lambda f: f.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    return controller


def _run(controller):
    script = [_frame("w", i) for i in range(3)] + [_frame("s", i) for i in range(4)] + [_frame("q", i) for i in range(4)]
    capture = FakeContinuousCapture(script)
    controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)
    return controller.status().recent_events


def test_capture_emits_partials_and_streamed_final(tmp_path: Path) -> None:
    runner = _StreamingSttRunner(["what", "what time", "what time is it"], "what time is it")
    events = _run(_controller(tmp_path, runner))

    partials = [e.summary.get("partial_transcript_text") for e in events if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_PARTIAL]
    assert partials == ["what", "what time", "what time is it"]
    completed = next(e for e in reversed(events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)
    assert completed.summary.get("normalized_transcript_text") == "what time is it"
    # Final came from the stream, not the one-shot fallback.
    assert runner.one_shot_calls == 0


def test_non_streaming_backend_falls_back_to_one_shot(tmp_path: Path) -> None:
    # A runner without open_stream (plain callable) must still work via one-shot.
    class _OneShot:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, request, asset) -> TranscriptionResult:
            self.calls += 1
            return TranscriptionResult.succeeded(trace_id=request.trace_id, text="hello there", backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    runner = _OneShot()
    events = _run(_controller(tmp_path, runner))
    partials = [e for e in events if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_PARTIAL]
    assert partials == []
    assert runner.calls == 1
    completed = next(e for e in reversed(events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)
    assert completed.summary.get("normalized_transcript_text") == "hello there"
