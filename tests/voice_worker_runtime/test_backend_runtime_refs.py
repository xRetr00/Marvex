from __future__ import annotations

import json
from pathlib import Path

from packages.voice_runtime import AudioFrame, SpeechSynthesisResult, TranscriptionResult
from packages.voice_worker_runtime import (
    FakeLocalAudioAdapter,
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerAudioRefStore,
    VoiceWorkerBackendRuntime,
    VoiceWorkerCommand,
    VoiceWorkerController,
    VoiceWorkerGeneratedAudioSink,
)


def test_worker_audio_ref_store_keeps_pcm_in_memory_without_safe_projection_leak() -> None:
    store = VoiceWorkerAudioRefStore()
    frames = (
        AudioFrame(frame_id="audio-ref-1", pcm=b"private-pcm", sample_rate=16_000, channel_count=1, duration_ms=100),
        AudioFrame(frame_id="audio-ref-2", pcm=b"more-private-pcm", sample_rate=16_000, channel_count=1, duration_ms=100),
    )

    ref = store.remember_frames(trace_id="trace-audio-ref", frames=frames)
    resolved = store.resolve(ref.audio_ref_id)
    projection = ref.safe_projection()

    assert resolved == frames
    assert projection["audio_ref_id"] == "memory://voice/captured/trace-audio-ref"
    assert projection["frame_count"] == 2
    assert projection["duration_ms"] == 200
    assert projection["byte_count"] == len(b"private-pcm") + len(b"more-private-pcm")
    assert projection["raw_audio_persisted"] is False
    assert "private-pcm" not in json.dumps(projection).lower()


def test_worker_test_stt_captures_audio_ref_for_runner_without_persistence(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True))
    audio_refs = VoiceWorkerAudioRefStore()
    observed: list[tuple[str, int, int]] = []

    def stt_runner(request, asset):
        frames = audio_refs.resolve(request.audio_ref_id)
        observed.append((asset.model_id, len(frames), sum(frame.duration_ms for frame in frames)))
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="private captured transcript", backend_id=request.backend_id or "moonshine-v2", duration_ms=request.duration_ms, language="en", confidence=0.88)

    backend_runtime = VoiceWorkerBackendRuntime(asset_manager=manager, audio_refs=audio_refs, stt_runner=stt_runner)
    controller = VoiceWorkerController(audio=FakeLocalAudioAdapter(), asset_manager=manager, backend_runtime=backend_runtime)

    result = controller.handle(VoiceWorkerCommand(command="test_stt", command_id="cmd-stt-capture"))
    serialized = json.dumps(result.safe_projection()).lower()

    assert observed == [("moonshine-v2", 4, 400)]
    assert result.event.summary["audio_ref_present"] is True
    assert result.event.summary["raw_audio_persisted"] is False
    assert "private captured transcript" not in serialized
    assert "\\x01\\x02" not in serialized


def test_worker_generated_audio_sink_creates_ref_without_persisting_audio(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "tts" / "kokoro-af-heart").mkdir(parents=True)
    (tmp_path / "voice-assets" / "tts" / "kokoro-voices").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="kokoro-af-heart", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-af-heart", explicit_user_triggered=True))
    manager.install_local(VoiceModelInstallRequest(model_id="kokoro-voices", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-voices", explicit_user_triggered=True))
    generated_audio = VoiceWorkerGeneratedAudioSink()
    observed: list[tuple[str, int]] = []

    def tts_runner(request, asset):
        ref = generated_audio.remember_audio(trace_id=request.trace_id, voice_id=request.voice_id, pcm=b"private-generated-audio", sample_rate=24_000)
        observed.append((asset.model_id, ref.byte_count))
        return SpeechSynthesisResult.succeeded(trace_id=request.trace_id, audio_ref=ref.audio_ref_id, backend_id=request.backend_id or "kokoro-onnx", voice_id=request.voice_id, duration_ms=120)

    backend_runtime = VoiceWorkerBackendRuntime(asset_manager=manager, generated_audio=generated_audio, tts_runner=tts_runner)
    controller = VoiceWorkerController(asset_manager=manager, backend_runtime=backend_runtime)

    result = controller.handle(VoiceWorkerCommand(command="test_tts", command_id="cmd-tts-sink", payload={"text": "sensitive response text"}))
    projection = generated_audio.safe_projection("memory://voice/generated/cmd-tts-sink/af_heart")
    serialized = json.dumps({"result": result.safe_projection(), "projection": projection}).lower()

    assert observed == [("kokoro-af-heart", len(b"private-generated-audio"))]
    assert projection["byte_count"] == len(b"private-generated-audio")
    assert projection["raw_audio_persisted"] is False
    assert result.event.summary["audio_ref_present"] is True
    assert "private-generated-audio" not in serialized
    assert "sensitive response text" not in serialized
