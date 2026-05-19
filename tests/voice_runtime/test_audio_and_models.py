from __future__ import annotations

import json

import pytest

from packages.voice_runtime import (
    AudioFrame,
    AudioInputRef,
    AudioRingBuffer,
    ChunkAggregator,
    SpeechSegmentAssembler,
    TranscriptionResult,
    VADDecision,
    VoiceErrorEnvelope,
    VoiceInputEvent,
    VoiceRuntimeConfig,
    WakeWordDetectionResult,
)


def test_audio_ring_buffer_keeps_preroll_and_never_projects_raw_audio() -> None:
    buffer = AudioRingBuffer(max_frames=3, pre_roll_ms=200)

    for index in range(5):
        buffer.append(AudioFrame(frame_id=f"frame-{index}", pcm=b"raw-audio", sample_rate=16000, duration_ms=40))

    assert [frame.frame_id for frame in buffer.frames] == ["frame-2", "frame-3", "frame-4"]
    projection = buffer.safe_projection()
    serialized = json.dumps(projection).lower()
    assert projection["frame_count"] == 3
    assert projection["raw_audio_persisted"] is False
    assert "raw-audio" not in serialized
    assert "pcm" not in serialized


def test_voice_input_event_requires_safe_audio_reference_or_summary() -> None:
    event = VoiceInputEvent(
        schema_version="1",
        trace_id="trace-voice-1",
        event_id="voice-event-1",
        source="wakeword",
        audio_ref=AudioInputRef(ref_id="audio-1", uri="memory://voice/audio-1", format="pcm_s16le"),
        safe_summary="wakeword-triggered buffered audio",
    )

    assert event.raw_audio_persisted is False
    assert event.safe_projection()["audio_ref"]["uri"] == "memory://voice/audio-1"
    with pytest.raises(ValueError):
        VoiceInputEvent(schema_version="1", trace_id="t", event_id="e", source="manual")


def test_vad_and_wakeword_safe_results_are_reason_coded() -> None:
    vad = VADDecision.speech_started(frame_count=4, confidence=0.82, noise_floor_db=-42.0)
    wakeword = WakeWordDetectionResult.detected(
        phrase="Hey Marvex",
        confidence=0.93,
        backend_id="sherpa-onnx-kws",
    )

    assert vad.is_speech is True
    assert vad.reason_code == "vad.speech_started"
    assert wakeword.detected is True
    assert wakeword.safe_projection()["raw_audio_persisted"] is False


def test_chunk_aggregator_finalizes_on_silence_and_duration_limits() -> None:
    aggregator = ChunkAggregator(max_utterance_ms=120, silence_cutoff_ms=80, tail_padding_ms=40)
    speech = VADDecision.speech_started(frame_count=1, confidence=0.9, noise_floor_db=-50.0)
    silence = VADDecision.silence(frame_count=1, confidence=0.2, noise_floor_db=-49.0)

    first = aggregator.accept(AudioFrame(frame_id="a", pcm=b"a", sample_rate=16000, duration_ms=40), speech)
    second = aggregator.accept(AudioFrame(frame_id="b", pcm=b"b", sample_rate=16000, duration_ms=40), silence)
    third = aggregator.accept(AudioFrame(frame_id="c", pcm=b"c", sample_rate=16000, duration_ms=40), silence)

    assert first.finalized is False
    assert second.finalized is False
    assert third.finalized is True
    assert third.reason_code == "chunk.finalized.silence_cutoff"
    assert third.safe_projection()["raw_audio_persisted"] is False


def test_speech_segment_assembler_prevents_runaway_recording() -> None:
    assembler = SpeechSegmentAssembler(max_utterance_ms=80)
    state = assembler.add(AudioFrame(frame_id="a", pcm=b"a", sample_rate=16000, duration_ms=40))
    final = assembler.add(AudioFrame(frame_id="b", pcm=b"b", sample_rate=16000, duration_ms=40))

    assert state.finalized is False
    assert final.finalized is True
    assert final.reason_code == "segment.max_utterance_duration"


def test_transcription_result_uses_safe_error_envelope_without_raw_backend_text() -> None:
    error = VoiceErrorEnvelope.backend_error(
        trace_id="trace-voice-1",
        backend_id="moonshine-v2",
        reason_code="model_not_installed",
    )
    result = TranscriptionResult.failed(
        trace_id="trace-voice-1",
        backend_id="moonshine-v2",
        duration_ms=12,
        error=error,
    )

    payload = result.safe_projection()
    assert payload["status"] == "failed"
    assert payload["backend_id"] == "moonshine-v2"
    assert payload["safe_error"]["details"] == {"reason_code": "model_not_installed", "backend_id": "moonshine-v2"}
    assert "raw" not in json.dumps(payload).lower()


def test_voice_runtime_config_defaults_to_no_hidden_recording_or_persistence() -> None:
    config = VoiceRuntimeConfig.default()

    assert config.wakeword.always_listening_enabled is False
    assert config.wakeword.phrase == "Hey Marvex"
    assert config.audio_retention.raw_audio_persistence_allowed is False
    assert config.audio_retention.transcript_persistence_allowed is False
    assert config.safe_projection()["hidden_recording_allowed"] is False
