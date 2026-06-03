from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from packages.voice_runtime import AudioFrame
from packages.voice_worker_runtime import VoiceAssetManager, VoiceModelInstallRequest, VoiceWorkerBackendRuntime
from packages.voice_worker_runtime import backend_runtime
from packages.voice_worker_runtime import model_adapters


def _install_asset(manager: VoiceAssetManager, root: Path, *, model_id: str, backend_id: str, model_kind: str, relative_path: str) -> None:
    target = root / relative_path
    target.mkdir(parents=True, exist_ok=True)
    result = manager.install_local(
        VoiceModelInstallRequest(model_id=model_id, backend_id=backend_id, model_kind=model_kind, relative_path=relative_path, explicit_user_triggered=True)
    )
    assert result.status == "installed"


def test_asset_manager_resolves_installed_path_without_projection_leak(tmp_path: Path) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    _install_asset(manager, root, model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2")

    path = manager.resolve_installed_path("moonshine-v2")
    serialized = json.dumps(manager.registry().model_dump(mode="json"))

    assert path == (root / "stt" / "moonshine-v2").resolve()
    assert str(root).lower() not in serialized.lower()
    assert manager.remove("moonshine-v2").removed is True
    assert manager.resolve_installed_path("moonshine-v2") is None


def test_default_moonshine_runner_invokes_transcriber_with_in_memory_frames(tmp_path: Path) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    _install_asset(manager, root, model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2")
    calls: list[tuple[str, int, int]] = []

    class FakeTranscriber:
        def __init__(self, model_path: str) -> None:
            self.model_path = model_path

        def transcribe_without_streaming(self, audio_data, sample_rate: int):
            calls.append((self.model_path, len(audio_data), sample_rate))
            return SimpleNamespace(lines=[SimpleNamespace(text="hello marvex", start_time=0.0, duration=0.25, words=[])])

        def close(self) -> None:
            calls.append(("closed", 0, 0))

    runtime = VoiceWorkerBackendRuntime(asset_manager=manager, module_loader=lambda name: SimpleNamespace(Transcriber=FakeTranscriber))
    audio_ref = runtime.remember_captured_frames(trace_id="trace-moonshine", frames=(AudioFrame(frame_id="f1", pcm=b"\x00\x00\xff\x7f", sample_rate=16_000, channel_count=1, duration_ms=100),))

    result = runtime.test_stt(trace_id="trace-moonshine", backend_id="moonshine-v2", audio_ref_id=audio_ref)
    result2 = runtime.test_stt(trace_id="trace-moonshine-2", backend_id="moonshine-v2", audio_ref_id=audio_ref)

    assert result.status == "succeeded"
    assert result2.status == "succeeded"
    assert result.text == "hello marvex"
    assert calls[0] == (str((root / "stt" / "moonshine-v2").resolve()), 2, 16_000)
    assert [call[0] for call in calls].count("closed") == 0
    assert len(calls) == 2
    assert "hello marvex" not in json.dumps(result.safe_projection()).lower()


def test_default_sensevoice_runner_invokes_funasr_automodel(tmp_path: Path) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    _install_asset(manager, root, model_id="sensevoice-small", backend_id="sensevoice-small", model_kind="stt", relative_path="stt/sensevoice-small")
    calls: list[tuple[str, int, int]] = []

    class FakeAutoModel:
        def __init__(self, model: str, **kwargs) -> None:
            calls.append((model, 0, 0))

        def generate(self, input, fs: int, **kwargs):
            calls.append(("generate", len(input), fs))
            return [{"text": "fallback transcript"}]

    runtime = VoiceWorkerBackendRuntime(asset_manager=manager, module_loader=lambda name: SimpleNamespace(AutoModel=FakeAutoModel))
    audio_ref = runtime.remember_captured_frames(trace_id="trace-sense", frames=(AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),))

    result = runtime.test_stt(trace_id="trace-sense", backend_id="sensevoice-small", audio_ref_id=audio_ref)

    assert result.status == "succeeded"
    assert result.text == "fallback transcript"
    assert calls[0][0] == str((root / "stt" / "sensevoice-small").resolve())
    assert calls[1] == ("generate", 2, 16_000)


def test_default_kokoro_runner_synthesizes_to_generated_audio_ref(tmp_path: Path) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    asset_dir = root / "tts" / "kokoro-af-heart"
    asset_dir.mkdir(parents=True)
    (asset_dir / "model.onnx").write_bytes(b"onnx")
    (asset_dir / "voices.npy").write_bytes(b"voices")
    manager.install_local(VoiceModelInstallRequest(model_id="kokoro-af-heart", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-af-heart", explicit_user_triggered=True))
    manager.install_local(VoiceModelInstallRequest(model_id="kokoro-voices", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-af-heart/voices.npy", explicit_user_triggered=True))
    calls: list[tuple[str, str, str]] = []

    class FakeAudio:
        def astype(self, dtype):
            return self

        def tobytes(self) -> bytes:
            return b"kokoro-pcm"

    class FakeKokoro:
        def __init__(self, model_path: str, voices_path: str) -> None:
            calls.append((model_path, voices_path, "init"))

        def create(self, text: str, voice: str):
            calls.append((text, voice, "create"))
            return FakeAudio(), 24_000

    runtime = VoiceWorkerBackendRuntime(asset_manager=manager, module_loader=lambda name: SimpleNamespace(Kokoro=FakeKokoro))

    result = runtime.test_tts(trace_id="trace-kokoro", backend_id="kokoro-onnx", voice_id="af_heart", text="hello there")

    assert result.status == "succeeded"
    assert result.audio_ref == "memory://voice/generated/trace-kokoro/af_heart"
    assert runtime.generated_audio.resolve(result.audio_ref) == b"kokoro-pcm"
    assert calls[0] == (str(asset_dir / "model.onnx"), str(asset_dir / "voices.npy"), "init")
    assert calls[1] == ("hello there", "af_heart", "create")


def test_kokoro_backend_is_not_ready_until_model_and_voices_are_installed(tmp_path: Path) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    kokoro_dir = root / "tts" / "kokoro"
    kokoro_dir.mkdir(parents=True)
    (kokoro_dir / "kokoro-v1.0.onnx").write_bytes(b"onnx")
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="kokoro-af-heart",
            backend_id="kokoro-onnx",
            model_kind="tts_voice",
            relative_path="tts/kokoro/kokoro-v1.0.onnx",
            explicit_user_triggered=True,
        )
    )
    runtime = VoiceWorkerBackendRuntime(asset_manager=manager, module_loader=lambda name: object())

    missing_voices = runtime.tts_status("kokoro-onnx", "af_heart")
    assert missing_voices["status"] == "not_ready"
    assert missing_voices["exact_blocker"] == "kokoro_voice_asset_missing_manual_install_required"

    (kokoro_dir / "voices-v1.0.bin").write_bytes(b"voices")
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="kokoro-voices",
            backend_id="kokoro-onnx",
            model_kind="tts_voice",
            relative_path="tts/kokoro/voices-v1.0.bin",
            explicit_user_triggered=True,
        )
    )

    ready = runtime.tts_status("kokoro-onnx", "af_heart")
    assert ready["status"] == "ready"
    assert ready["exact_blocker"] is None


def test_sherpa_kws_runner_normalizes_multiword_keyword_aliases(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    model_dir = root / "wakeword" / "hey-marvex" / "nested"
    model_dir.mkdir(parents=True)
    for name in ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx"):
        (model_dir / name).write_bytes(b"onnx")
    (model_dir / "tokens.txt").write_text("▁HE 1\nY 2\n▁MAR 3\nVE 4\nX 5\n", encoding="utf-8")
    (model_dir / "keywords.txt").write_text("▁HE Y ▁MAR VE X :1.5 #0.2 @HEY MARVEX\n", encoding="utf-8")
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="hey-marvex",
            backend_id="sherpa-onnx-kws",
            model_kind="wakeword",
            relative_path="wakeword/hey-marvex",
            explicit_user_triggered=True,
        )
    )

    class FakeResult:
        keyword = "HEY_MARVEX"
        confidence = 0.9

    class FakeStream:
        result = FakeResult()

        def accept_waveform(self, sample_rate, samples):
            assert sample_rate == 16_000
            assert samples

    class FakeKeywordSpotter:
        def __init__(self, **kwargs):
            keyword_text = Path(kwargs["keywords_file"]).read_text(encoding="utf-8")
            assert "@HEY_MARVEX" in keyword_text
            assert "@HEY MARVEX" not in keyword_text
            assert kwargs["keywords_threshold"] == 0.72

        def create_stream(self):
            return FakeStream()

        def decode_stream(self, stream):
            assert isinstance(stream, FakeStream)

    monkeypatch.setattr(
        model_adapters,
        "import_module",
        lambda name: SimpleNamespace(KeywordSpotter=FakeKeywordSpotter) if name == "sherpa_onnx" else __import__(name),
    )
    monkeypatch.setattr(
        backend_runtime,
        "import_module",
        lambda name: SimpleNamespace(KeywordSpotter=FakeKeywordSpotter) if name == "sherpa_onnx" else __import__(name),
    )
    runtime = VoiceWorkerBackendRuntime(asset_manager=manager)

    result = runtime.test_wakeword(
        trace_id="trace-kws",
        backend_id="sherpa-onnx-kws",
        frames=(AudioFrame(frame_id="f1", pcm=b"\x01\x00\x02\x00", sample_rate=16_000, channel_count=1, duration_ms=100),),
        phrase="Hey Marvex",
        threshold=0.72,
    )

    assert result.detected is True


def test_default_piper_runner_synthesizes_chunks_to_generated_audio_ref(tmp_path: Path) -> None:
    root = tmp_path / "voice-assets"
    manager = VoiceAssetManager(asset_root=root)
    asset_dir = root / "tts" / "piper-default"
    asset_dir.mkdir(parents=True)
    (asset_dir / "voice.onnx").write_bytes(b"onnx")
    (asset_dir / "voice.onnx.json").write_text("{}", encoding="utf-8")
    manager.install_local(VoiceModelInstallRequest(model_id="piper-default", backend_id="piper-tts", model_kind="tts_voice", relative_path="tts/piper-default", explicit_user_triggered=True))
    calls: list[str] = []

    class FakeVoice:
        @staticmethod
        def load(model_path: str, config_path: str | None = None):
            calls.append(f"load:{model_path}:{config_path}")
            return FakeVoice()

        def synthesize(self, text: str):
            calls.append(f"synthesize:{text}")
            return [SimpleNamespace(audio_int16_bytes=b"one", sample_rate=22_050), SimpleNamespace(audio_int16_bytes=b"two", sample_rate=22_050)]

    runtime = VoiceWorkerBackendRuntime(asset_manager=manager, module_loader=lambda name: SimpleNamespace(PiperVoice=FakeVoice))

    result = runtime.test_tts(trace_id="trace-piper", backend_id="piper-tts", voice_id="piper-default", text="speak now")

    assert result.status == "succeeded"
    assert runtime.generated_audio.resolve(result.audio_ref or "") == b"onetwo"
    assert calls == [f"load:{asset_dir / 'voice.onnx'}:{asset_dir / 'voice.onnx.json'}", "synthesize:speak now"]
