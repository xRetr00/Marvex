"""Tests for the spoken-language gate that lets the English-only Moonshine path
ignore non-English utterances (SpeechBrain language ID at endpoint)."""

from __future__ import annotations

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
from packages.voice_worker_runtime.model_adapters import LanguageIdRunner
from packages.voice_worker_runtime.models import VoiceWorkerEventType


def _frame(tag: str, i: int) -> AudioFrame:
    return AudioFrame(frame_id=f"{tag}{i}", pcm=b"\x01\x00" * 160, sample_rate=16_000, channel_count=1, duration_ms=100)


def _install_langid(manager: VoiceAssetManager, tmp_path: Path) -> None:
    model_dir = tmp_path / "voice-assets" / "langid" / "voxlingua107-ecapa"
    model_dir.mkdir(parents=True)
    (model_dir / "hyperparams.yaml").write_text("fake", encoding="utf-8")
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="speechbrain-langid",
            backend_id="speechbrain-langid",
            model_kind="langid",
            relative_path="langid/voxlingua107-ecapa/hyperparams.yaml",
            explicit_user_triggered=True,
        )
    )


def test_language_id_runner_is_fail_open_when_model_missing(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    runner = LanguageIdRunner(asset_manager=manager, classifier_factory=lambda _dir: (lambda _s, _r: ("ar", 0.99)))
    # Model not installed -> None (allow), never even calls the classifier.
    assert runner.detect((_frame("s", 0),)) is None


def test_language_id_runner_reports_verdict_when_installed(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    _install_langid(manager, tmp_path)
    runner = LanguageIdRunner(asset_manager=manager, classifier_factory=lambda _dir: (lambda _s, _r: ("AR", 0.97)))
    assert runner.detect((_frame("s", 0),)) == ("ar", 0.97)


def _controller_with_langid(tmp_path: Path, *, langid):
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex", explicit_user_triggered=True))
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True))

    def wakeword_runner(frames, asset, *, phrase, threshold):
        if any(f.frame_id.startswith("w") for f in frames):
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=asset.backend_id, reason_code="wakeword.not_detected")

    def stt_runner(request, asset):
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="what time is it", backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    cfg = VoiceWorkerConfig.default()
    cfg = cfg.model_copy(update={"wakeword": cfg.wakeword.model_copy(update={"enabled": True}), "vad": cfg.vad.model_copy(update={"silence_timeout_ms": 300, "tail_padding_ms": 100, "max_utterance_ms": 3000})})
    controller = VoiceWorkerController(
        config=cfg, asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner, stt_runner=stt_runner, langid_runner=langid),
    )
    controller._vad_decider = lambda f: f.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    return controller


class _FakeLangId:
    def __init__(self, verdict):
        self._verdict = verdict
    def detect(self, frames):
        return self._verdict


def _run_capture(controller):
    script = [_frame("w", i) for i in range(3)] + [_frame("s", i) for i in range(4)] + [_frame("q", i) for i in range(4)]
    capture = FakeContinuousCapture(script)
    controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)
    return next(e for e in reversed(controller.status().recent_events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)


def test_confident_non_english_is_dropped_with_reason(tmp_path: Path) -> None:
    controller = _controller_with_langid(tmp_path, langid=_FakeLangId(("ar", 0.95)))
    completed = _run_capture(controller)
    assert completed.summary.get("accepted_transcript_present") is False
    assert completed.summary.get("transcript_rejected_reason") == "non_english_ignored"
    assert completed.summary.get("detected_language") == "ar"


def test_english_verdict_is_accepted(tmp_path: Path) -> None:
    controller = _controller_with_langid(tmp_path, langid=_FakeLangId(("en", 0.99)))
    completed = _run_capture(controller)
    assert completed.summary.get("accepted_transcript_present") is True
    assert completed.summary.get("normalized_transcript_text") == "what time is it"


def test_low_confidence_non_english_falls_through_to_allow(tmp_path: Path) -> None:
    controller = _controller_with_langid(tmp_path, langid=_FakeLangId(("ar", 0.2)))
    completed = _run_capture(controller)
    assert completed.summary.get("accepted_transcript_present") is True


def test_no_verdict_fails_open(tmp_path: Path) -> None:
    controller = _controller_with_langid(tmp_path, langid=_FakeLangId(None))
    completed = _run_capture(controller)
    assert completed.summary.get("accepted_transcript_present") is True
