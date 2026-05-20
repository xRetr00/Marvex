from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from packages.voice_runtime import AudioFrame, SpeechSynthesisRequest, TranscriptionRequest
from packages.voice_worker_runtime import VoiceAssetManager, VoiceModelInstallRequest, VoiceWorkerAudioRefStore, VoiceWorkerGeneratedAudioSink
from packages.voice_worker_runtime.model_adapters import KokoroOnnxTtsRunner, MoonshineSttRunner, PiperTtsRunner, SenseVoiceSttRunner


def _install(manager: VoiceAssetManager, *, model_id: str, backend_id: str, model_kind: str, relative_path: str):
    target = manager.asset_root / relative_path
    target.mkdir(parents=True, exist_ok=True)
    return manager.install_local(VoiceModelInstallRequest(model_id=model_id, backend_id=backend_id, model_kind=model_kind, relative_path=relative_path, explicit_user_triggered=True))


def test_moonshine_runner_transcribes_resolved_audio_ref_without_rendering_pcm_or_text(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2")
    audio_refs = VoiceWorkerAudioRefStore()
    audio_ref = audio_refs.remember_frames(trace_id="trace-moonshine", frames=(AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),))
    observed: dict[str, object] = {}

    class FakeTranscriber:
        def __init__(self, model_path: str) -> None:
            observed["model_path"] = model_path

        def transcribe_without_streaming(self, audio_data, sample_rate: int = 16000):
            observed["sample_rate"] = sample_rate
            observed["audio_count"] = len(audio_data)
            return SimpleNamespace(lines=[SimpleNamespace(text="private moonshine transcript", start=0.0, end=0.1)])

        def close(self) -> None:
            observed["closed"] = True

    runner = MoonshineSttRunner(asset_manager=manager, audio_refs=audio_refs, transcriber_factory=FakeTranscriber)
    result = runner(TranscriptionRequest(trace_id="trace-moonshine", audio_ref_id=audio_ref.audio_ref_id, duration_ms=100, backend_id="moonshine-v2"), asset)
    serialized = json.dumps(result.safe_projection()).lower()

    assert result.status == "succeeded"
    assert result.text == "private moonshine transcript"
    assert str(observed["model_path"]).endswith("stt\\moonshine-v2") or str(observed["model_path"]).endswith("stt/moonshine-v2")
    assert observed["sample_rate"] == 16000
    assert observed["audio_count"] == 2
    assert observed["closed"] is True
    assert "private moonshine transcript" not in serialized
    assert "\\x00" not in serialized


def test_sensevoice_runner_uses_funasr_generate_from_resolved_audio_ref(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="sensevoice-small", backend_id="sensevoice-small", model_kind="stt", relative_path="stt/sensevoice-small")
    audio_refs = VoiceWorkerAudioRefStore()
    audio_ref = audio_refs.remember_frames(trace_id="trace-sense", frames=(AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),))
    observed: dict[str, object] = {}

    class FakeAutoModel:
        def __init__(self, **kwargs) -> None:
            observed["model"] = kwargs["model"]

        def generate(self, *, input, fs: int, language="auto"):
            observed["input_count"] = len(input)
            observed["sample_rate"] = fs
            observed["language"] = language
            return [{"text": "private sensevoice transcript", "timestamps": [[0, 100]]}]

    runner = SenseVoiceSttRunner(asset_manager=manager, audio_refs=audio_refs, automodel_factory=FakeAutoModel)
    result = runner(TranscriptionRequest(trace_id="trace-sense", audio_ref_id=audio_ref.audio_ref_id, duration_ms=100, backend_id="sensevoice-small", language_hint="en"), asset)

    assert result.status == "succeeded"
    assert result.text == "private sensevoice transcript"
    assert str(observed["model"]).endswith("stt\\sensevoice-small") or str(observed["model"]).endswith("stt/sensevoice-small")
    assert observed["input_count"] == 2
    assert observed["sample_rate"] == 16000
    assert observed["language"] == "en"
    assert result.segments[0]["text_present"] is True


def test_kokoro_runner_synthesizes_to_generated_audio_ref_without_rendering_text(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset_dir = manager.asset_root / "tts" / "kokoro-af-heart"
    asset_dir.mkdir(parents=True)
    (asset_dir / "model.onnx").write_bytes(b"model")
    (asset_dir / "voices.npy").write_bytes(b"voices")
    asset = manager.install_local(VoiceModelInstallRequest(model_id="kokoro-af-heart", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-af-heart", explicit_user_triggered=True))
    generated_audio = VoiceWorkerGeneratedAudioSink()
    observed: dict[str, object] = {}

    class FakeKokoro:
        def __init__(self, model_path: str, voices_path: str) -> None:
            observed["model_path"] = model_path
            observed["voices_path"] = voices_path

        def create(self, text: str, voice: str, speed: float = 1.0, lang: str = "en-us"):
            observed["text"] = text
            observed["voice"] = voice
            return ([0.5, -0.5], 24000)

    runner = KokoroOnnxTtsRunner(asset_manager=manager, generated_audio=generated_audio, kokoro_factory=FakeKokoro)
    result = runner(SpeechSynthesisRequest(trace_id="trace-kokoro", text="  private   response  ", voice_id="af_heart", backend_id="kokoro-onnx"), asset)
    serialized = json.dumps({"result": result.safe_projection(), "audio": generated_audio.safe_projection(result.audio_ref or "")}).lower()

    assert result.status == "succeeded"
    assert result.audio_ref == "memory://voice/generated/trace-kokoro/af_heart"
    assert generated_audio.resolve(result.audio_ref) != b""
    assert observed["text"] == "private response"
    assert observed["voice"] == "af_heart"
    assert "private response" not in serialized
    assert "raw_generated_audio_persisted" in serialized


def test_piper_runner_synthesizes_chunks_to_generated_audio_ref(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset_dir = manager.asset_root / "tts" / "piper-default"
    asset_dir.mkdir(parents=True)
    (asset_dir / "voice.onnx").write_bytes(b"model")
    (asset_dir / "voice.onnx.json").write_text("{}", encoding="utf-8")
    asset = manager.install_local(VoiceModelInstallRequest(model_id="piper-default", backend_id="piper-tts", model_kind="tts_voice", relative_path="tts/piper-default", explicit_user_triggered=True))
    generated_audio = VoiceWorkerGeneratedAudioSink()
    observed: dict[str, object] = {}

    class FakeVoice:
        def synthesize(self, text: str):
            observed["text"] = text
            return [SimpleNamespace(audio_int16_bytes=b"\x01\x00"), SimpleNamespace(audio_int16_bytes=b"\x02\x00")]

    def fake_load(model_path: str, config_path: str | None = None):
        observed["model_path"] = model_path
        observed["config_path"] = config_path
        return FakeVoice()

    runner = PiperTtsRunner(asset_manager=manager, generated_audio=generated_audio, voice_loader=fake_load)
    result = runner(SpeechSynthesisRequest(trace_id="trace-piper", text="private piper response", voice_id="piper-default", backend_id="piper-tts"), asset)

    assert result.status == "succeeded"
    assert result.audio_ref == "memory://voice/generated/trace-piper/piper-default"
    assert generated_audio.resolve(result.audio_ref) == b"\x01\x00\x02\x00"
    assert str(observed["model_path"]).endswith("voice.onnx")
    assert str(observed["config_path"]).endswith("voice.onnx.json")
    assert observed["text"] == "private piper response"
