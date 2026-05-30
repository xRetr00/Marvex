"""Tests for the continuous wake-word + command loop (root voice fix).

The loop feeds a gap-free mic stream to the KWS (what the streaming zipformer
needs) and, on detection, captures the command from the SAME stream.
"""

from pathlib import Path

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
from packages.voice_worker_runtime.models import VoiceWorkerEventType


def _frame(tag: str, i: int) -> AudioFrame:
    return AudioFrame(frame_id=f"{tag}{i}", pcm=b"\x01\x00" * 160, sample_rate=16_000, channel_count=1, duration_ms=100)


def _install(tmp_path: Path) -> VoiceAssetManager:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex", explicit_user_triggered=True)
    )
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True)
    )
    return manager


def _enabled_config() -> VoiceWorkerConfig:
    cfg = VoiceWorkerConfig.default()
    return cfg.model_copy(
        update={
            "wakeword": cfg.wakeword.model_copy(update={"enabled": True}),
            "vad": cfg.vad.model_copy(update={"silence_timeout_ms": 300, "tail_padding_ms": 100, "max_utterance_ms": 3000}),
        }
    )


def _controller(tmp_path: Path):
    manager = _install(tmp_path)
    stt_calls = []

    def wakeword_runner(frames, asset, *, phrase, threshold):
        detected = any(f.frame_id.startswith("w") for f in frames)
        if detected:
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=asset.backend_id, reason_code="wakeword.not_detected")

    def stt_runner(request, asset):
        stt_calls.append(request.audio_ref_id)
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="what time is it", backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    controller = VoiceWorkerController(
        config=_enabled_config(), asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner, stt_runner=stt_runner),
    )
    controller._vad_decider = lambda f: f.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    return controller, stt_calls


def test_wake_detect_then_command_transcript_over_continuous_stream(tmp_path: Path):
    controller, stt_calls = _controller(tmp_path)
    # 3 wake frames -> detection; then command speech then silence -> endpoint.
    script = (
        [_frame("w", i) for i in range(3)]
        + [_frame("s", i) for i in range(4)]
        + [_frame("q", i) for i in range(4)]
    )
    capture = FakeContinuousCapture(script)
    result = controller.run_wake_listen_loop(
        capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0
    )

    assert result["started"] is True
    assert result["detections"] >= 1
    assert stt_calls, "command STT should have run after wake"
    events = [e.event_type for e in controller.status().recent_events]
    assert VoiceWorkerEventType.WAKEWORD_DETECTED in events
    completed = next(e for e in reversed(controller.status().recent_events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)
    assert completed.summary.get("transcript_text") == "what time is it"


def test_no_detection_when_no_wake_frames(tmp_path: Path):
    controller, stt_calls = _controller(tmp_path)
    script = [_frame("q", i) for i in range(12)]  # all silence, no wake
    capture = FakeContinuousCapture(script)
    result = controller.run_wake_listen_loop(
        capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0
    )
    assert result["detections"] == 0
    assert not stt_calls


def test_loop_refuses_when_wakeword_disabled(tmp_path: Path):
    manager = _install(tmp_path)
    cfg = VoiceWorkerConfig.default().model_copy(update={"wakeword": VoiceWorkerConfig.default().wakeword.model_copy(update={"enabled": False})})
    controller = VoiceWorkerController(config=cfg, asset_manager=manager, backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager))
    capture = FakeContinuousCapture([])
    result = controller.run_wake_listen_loop(capture=capture, should_stop=lambda: True)
    assert result["started"] is False
    assert result["reason_code"] == "wakeword_not_enabled"


def test_fake_capture_delivers_frames_in_order():
    cap = FakeContinuousCapture([_frame("a", 0), _frame("b", 1)])
    cap.start()
    assert cap.read().frame_id == "a0"
    assert cap.read().frame_id == "b1"
    assert cap.read() is None
    assert cap.remaining() == 0
