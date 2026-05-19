from __future__ import annotations

from packages.voice_runtime import (
    AudioCaptureRequest,
    AudioCaptureResult,
    AudioFrame,
    NoiseFloorEstimate,
    PartialTranscriptBuffer,
    SherpaOnnxWakeWordAdapter,
    SileroVadAdapter,
    SpeechSegment,
    WebRtcVadAdapter,
)


def test_wakeword_adapter_is_sherpa_backed_and_policy_visible() -> None:
    adapter = SherpaOnnxWakeWordAdapter(phrase="Hey Marvex", threshold=0.72)
    result = adapter.detect((AudioFrame(frame_id="f", pcm=b"0", sample_rate=16000, duration_ms=20),))
    health = adapter.health()

    assert adapter.backend_id == "sherpa-onnx-kws"
    assert result.detected is False
    assert result.phrase == "Hey Marvex"
    assert health.package_name == "sherpa-onnx"


def test_vad_adapters_return_deterministic_safe_decisions() -> None:
    frame = AudioFrame(frame_id="f", pcm=b"\x01", sample_rate=16000, duration_ms=20)

    assert SileroVadAdapter().decide((frame,)).reason_code == "vad.speech_started"
    assert WebRtcVadAdapter().decide(()).reason_code == "vad.silence"


def test_capture_segments_noise_and_partial_transcripts_are_safe_summaries() -> None:
    capture = AudioCaptureRequest(trace_id="trace-1", source="push_to_talk", sample_rate=16000)
    result = AudioCaptureResult.from_request(capture, frame_count=4, duration_ms=160)
    segment = SpeechSegment(segment_id="seg-1", start_ms=0, end_ms=160, frame_count=4, noise=NoiseFloorEstimate(db=-44.0))
    partials = PartialTranscriptBuffer(max_items=2)

    partials.add("hello")
    partials.add("hello world")
    partials.add("final hello world")

    assert result.raw_audio_persisted is False
    assert segment.duration_ms == 160
    assert partials.safe_projection()["partial_count"] == 2
    assert "hello" not in str(partials.safe_projection()).lower()
