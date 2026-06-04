"""Tests for the continuous wake-word + command loop (root voice fix).

The loop feeds a gap-free mic stream to the KWS (what the streaming zipformer
needs) and, on detection, captures the command from the SAME stream.
"""

from pathlib import Path

from packages.voice_runtime import AudioFrame, TranscriptionResult, WakeWordDetectionResult
from packages.voice_worker_runtime import (
    FakeLocalAudioAdapter,
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerBackendRuntime,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
)
from packages.voice_worker_runtime.continuous_capture import FakeContinuousCapture
from packages.voice_worker_runtime.models import VoiceWorkerEventType
from packages.voice_worker_runtime.wake_enrollment import wake_reference_dir, write_wake_reference_wav


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


def _install_stt_only_with_local_wake_refs(tmp_path: Path) -> VoiceAssetManager:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True)
    )
    ref_dir = wake_reference_dir(manager.asset_root)
    write_wake_reference_wav(ref_dir / "hey-marvex-01.wav", [b"\x01\x00" * 1600], sample_rate=16_000)
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
    assert completed.summary.get("normalized_transcript_text") == "what time is it"


def test_capture_suppressed_while_marvex_is_speaking(tmp_path: Path):
    """Half-duplex gate: the loudspeaker's TTS must never be captured + re-sent.

    While playback is active the mic hears Marvex's own voice. Without a gate the
    wake/probe path treats that as a wake and the command capture transcribes the
    TTS, looping it back in as a user turn (the reported STT-captures-TTS bug).
    """

    controller, stt_calls = _controller(tmp_path)
    controller._playback_active = True  # Marvex is speaking right now.
    script = (
        [_frame("w", i) for i in range(3)]
        + [_frame("s", i) for i in range(4)]
        + [_frame("q", i) for i in range(4)]
    )
    capture = FakeContinuousCapture(script)
    result = controller.run_wake_listen_loop(
        capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0
    )

    assert result["detections"] == 0
    assert stt_calls == [], "STT must not run on Marvex's own TTS playback"


def test_wake_detection_does_not_speak_tts_cue_before_command_capture(tmp_path: Path):
    manager = _install(tmp_path)
    spoken: list[str] = []

    def wakeword_runner(frames, asset, *, phrase, threshold):
        if any(f.frame_id.startswith("w") for f in frames):
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=asset.backend_id, reason_code="wakeword.not_detected")

    def stt_runner(request, asset):
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="open dashboard", backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    def tts_runner(request, asset):
        spoken.append(request.text)
        raise AssertionError("wake detection must not play a spoken cue while command capture is about to start")

    controller = VoiceWorkerController(
        config=_enabled_config(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner, stt_runner=stt_runner, tts_runner=tts_runner),
    )
    controller._vad_decider = lambda f: f.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    capture = FakeContinuousCapture([_frame("w", i) for i in range(3)] + [_frame("s", i) for i in range(3)] + [_frame("q", i) for i in range(4)])

    controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)

    assert spoken == []
    events = controller.status().recent_events
    wake_index = next(i for i, event in enumerate(events) if event.event_type == VoiceWorkerEventType.WAKEWORD_DETECTED)
    vad_index = next(i for i, event in enumerate(events) if event.event_type == VoiceWorkerEventType.VAD_SPEECH_STARTED)
    assert wake_index < vad_index
    assert not any(event.event_type == VoiceWorkerEventType.TTS_STARTED and event.summary.get("listening_cue") is True for event in events)


def test_local_wake_references_replace_sherpa_asset_gate(tmp_path: Path):
    manager = _install_stt_only_with_local_wake_refs(tmp_path)
    wake_assets = []
    stt_calls = []

    def wakeword_runner(frames, asset, *, phrase, threshold):
        wake_assets.append(asset.backend_id)
        detected = any(f.frame_id.startswith("w") for f in frames)
        if detected:
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold, backend_id=asset.backend_id)
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=asset.backend_id, reason_code="wakeword.not_detected")

    def stt_runner(request, asset):
        stt_calls.append(request.audio_ref_id)
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="local wake works", backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    controller = VoiceWorkerController(
        config=_enabled_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner, stt_runner=stt_runner),
    )
    controller._vad_decider = lambda f: f.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    script = [_frame("w", i) for i in range(3)] + [_frame("s", i) for i in range(3)] + [_frame("q", i) for i in range(4)]
    capture = FakeContinuousCapture(script)

    result = controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)

    assert result["started"] is True
    assert result["detections"] >= 1
    assert wake_assets and set(wake_assets) == {"local-wake"}
    assert stt_calls
    completed = next(e for e in reversed(controller.status().recent_events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)
    assert completed.summary.get("normalized_transcript_text") == "local wake works"


def test_loop_emits_diagnostics_for_field_observability(tmp_path: Path):
    controller, _ = _controller(tmp_path)
    script = (
        [_frame("w", i) for i in range(3)]
        + [_frame("s", i) for i in range(4)]
        + [_frame("q", i) for i in range(4)]
    )
    capture = FakeContinuousCapture(script)
    events: list[dict] = []
    controller.run_wake_listen_loop(
        capture=capture,
        should_stop=lambda: capture.remaining() == 0,
        frames_per_decode=3,
        idle_timeout=0.0,
        on_diagnostic=events.append,
    )
    kinds = [e.get("event") for e in events]
    assert "wake_listen_started" in kinds, kinds
    assert "wake_listen_detected" in kinds, kinds
    assert "wake_listen_stopped" in kinds, kinds
    stopped = next(e for e in events if e.get("event") == "wake_listen_stopped")
    assert stopped["frames_read"] >= 3
    assert stopped["detections"] >= 1
    # Audio level is reported so silent-capture vs keyword-mismatch is diagnosable.
    assert "audio_rms" in stopped
    assert stopped["audio_rms"] >= 0.0


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


def test_listen_command_queues_manual_capture_while_continuous_active(tmp_path: Path):
    controller, stt_calls = _controller(tmp_path)
    controller._continuous_active = True  # simulate the wake loop owning the mic
    result = controller.handle(VoiceWorkerCommand(command="listen", command_id="c-listen"))
    # No chunked capture / STT runs in the command handler; the continuous loop
    # will consume the queued request from its own stream.
    assert not stt_calls
    assert result.event.summary.get("manual_listen_queued") is True


def test_continuous_loop_services_queued_manual_listen_without_wake(tmp_path: Path):
    controller, stt_calls = _controller(tmp_path)
    controller._manual_listen_trace_id = "trace-manual-listen"
    script = [_frame("s", i) for i in range(4)] + [_frame("q", i) for i in range(4)]
    capture = FakeContinuousCapture(script)

    result = controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)

    assert result["detections"] == 0
    assert stt_calls
    completed = next(e for e in reversed(controller.status().recent_events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)
    assert completed.trace_id == "trace-manual-listen"
    assert completed.summary.get("normalized_transcript_text") == "what time is it"


def test_queued_manual_listen_rejects_short_vad_blip_before_stt(tmp_path: Path):
    controller, stt_calls = _controller(tmp_path)
    controller.config = controller.config.model_copy(update={"vad": controller.config.vad.model_copy(update={"min_speech_ms": 300})})
    controller._manual_listen_trace_id = "trace-short-noise"
    script = [_frame("s", 0)] + [_frame("q", i) for i in range(4)]
    capture = FakeContinuousCapture(script)

    controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)

    assert not stt_calls
    ended = next(e for e in reversed(controller.status().recent_events) if e.event_type == VoiceWorkerEventType.VAD_SPEECH_ENDED)
    assert ended.summary.get("reason_code") == "speech_too_short"


def test_queued_manual_listen_does_not_expose_filler_transcript(tmp_path: Path):
    manager = _install(tmp_path)

    def wakeword_runner(frames, asset, *, phrase, threshold):
        return WakeWordDetectionResult(detected=False, phrase=phrase, confidence=0.0, backend_id=asset.backend_id, reason_code="wakeword.not_detected")

    def stt_runner(request, asset):
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="Eh?", backend_id=asset.backend_id, duration_ms=request.duration_ms, language="en", segments=())

    controller = VoiceWorkerController(
        config=_enabled_config(),
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner, stt_runner=stt_runner),
    )
    controller._vad_decider = lambda frame: frame.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    controller._manual_listen_trace_id = "trace-filler"
    capture = FakeContinuousCapture([_frame("s", i) for i in range(3)] + [_frame("q", i) for i in range(4)])

    controller.run_wake_listen_loop(capture=capture, should_stop=lambda: capture.remaining() == 0, frames_per_decode=3, idle_timeout=0.0)

    completed = next(e for e in reversed(controller.status().recent_events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED)
    assert completed.summary.get("transcript_rejected_reason") == "short_filler_or_noise"
    assert "normalized_transcript_text" not in completed.summary


def test_record_wake_reference_uses_continuous_capture_when_available(tmp_path: Path):
    manager = _install(tmp_path)
    capture = FakeContinuousCapture([_frame("q", 0), _frame("s", 1), _frame("s", 2), _frame("q", 3), _frame("q", 4), _frame("q", 5)])

    class ChunkedAudioMustNotBeUsed:
        capture_calls = 0

        def capture_frames(self, *, device_id, sample_rate, channel_count, frame_count):
            self.capture_calls += 1
            raise AssertionError("wake enrollment must not use chunked capture_frames when continuous capture is available")

        def list_input_devices(self):
            return ()

        def list_output_devices(self):
            return ()

        def stop_playback(self):
            return None

    audio = ChunkedAudioMustNotBeUsed()
    controller = VoiceWorkerController(
        config=_enabled_config(),
        audio=audio,
        asset_manager=manager,
        backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager),
        continuous_capture_factory=lambda: capture,
    )
    controller._vad_decider = lambda frame: frame.frame_id.startswith("s")

    result = controller.handle(VoiceWorkerCommand(command="record_wake_reference", command_id="c-ref"))

    assert audio.capture_calls == 0
    assert capture.active() is False
    assert result.event.summary.get("record_wake_reference") is True
    assert result.event.summary.get("capture_mode") == "continuous"
    assert result.event.summary.get("reference_count") == 1


def test_fake_capture_delivers_frames_in_order():
    cap = FakeContinuousCapture([_frame("a", 0), _frame("b", 1)])
    cap.start()
    assert cap.read().frame_id == "a0"
    assert cap.read().frame_id == "b1"
    assert cap.read() is None
    assert cap.remaining() == 0
