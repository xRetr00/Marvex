from __future__ import annotations

from packages.voice_runtime import (
    AudioCaptureRequest,
    AudioCaptureResult,
    AudioFrame,
    NoiseFloorEstimate,
    PartialTranscriptBuffer,
    SentenceBoundaryDetector,
    SentenceClampPolicy,
    SherpaOnnxWakeWordAdapter,
    SileroVadAdapter,
    StreamingTextChunk,
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


def test_vad_adapters_return_safe_silence_for_empty_or_invalid_audio() -> None:
    frame = AudioFrame(frame_id="f", pcm=b"\x01", sample_rate=16000, duration_ms=20)

    assert SileroVadAdapter().decide((frame,)).reason_code == "vad.silence"
    assert WebRtcVadAdapter().decide(()).reason_code == "vad.silence"


def test_webrtc_vad_adapter_invokes_package_vad_when_frames_are_present() -> None:
    calls: list[tuple[bytes, int, int]] = []

    class FakeVad:
        def __init__(self, aggressiveness: int) -> None:
            self.aggressiveness = aggressiveness

        def is_speech(self, pcm: bytes, sample_rate: int) -> bool:
            calls.append((pcm, sample_rate, self.aggressiveness))
            return True

    adapter = WebRtcVadAdapter(module_loader=lambda name: type("FakeWebRtcVadModule", (), {"Vad": FakeVad}))
    frame = AudioFrame(frame_id="f", pcm=b"\x01\x00" * 160, sample_rate=16000, duration_ms=20)

    decision = adapter.decide((frame,))

    assert decision.is_speech is True
    assert decision.reason_code == "vad.speech_started"
    assert calls == [(frame.pcm, 16000, 2)]


def test_silero_vad_adapter_invokes_package_helpers_when_available() -> None:
    calls: list[tuple[int, int]] = []

    class FakeSileroModule:
        @staticmethod
        def load_silero_vad():
            return "fake-model"

        @staticmethod
        def read_audio(source, sampling_rate: int = 16000):
            del source
            return [0.0, 0.5]

        @staticmethod
        def get_speech_timestamps(audio, model, sampling_rate: int = 16000, threshold: float = 0.5):
            assert model == "fake-model"
            calls.append((len(audio), sampling_rate))
            return [{"start": 0, "end": 2}]

    adapter = SileroVadAdapter(module_loader=lambda name: FakeSileroModule)
    frame = AudioFrame(frame_id="f", pcm=b"\x01\x00" * 160, sample_rate=16000, duration_ms=20)

    decision = adapter.decide((frame,))

    assert decision.is_speech is True
    assert decision.reason_code == "vad.speech_started"
    assert calls == [(160, 16000)]


def test_sentence_boundary_detector_uses_stream2sentence_when_available() -> None:
    class FakeStream2Sentence:
        @staticmethod
        def generate_sentences(chunks):
            text = "".join(chunks)
            if text:
                yield text.strip()

    detector = SentenceBoundaryDetector(
        SentenceClampPolicy(max_chars=80),
        module_loader=lambda name: FakeStream2Sentence,
    )

    ready = detector.accept(StreamingTextChunk(text="One sentence from stream", index=0, final=True))

    assert [item.text for item in ready] == ["One sentence from stream"]


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
