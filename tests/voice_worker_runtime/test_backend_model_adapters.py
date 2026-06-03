from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from packages.voice_runtime import AudioFrame, SpeechSynthesisRequest, TranscriptionRequest
from packages.voice_worker_runtime import VoiceAssetManager, VoiceModelInstallRequest, VoiceWorkerAudioRefStore, VoiceWorkerGeneratedAudioSink
from packages.voice_worker_runtime.model_adapters import KokoroOnnxTtsRunner, MoonshineSttRunner, PiperTtsRunner, SenseVoiceSttRunner, SherpaOnnxKwsRunner, SherpaOnnxSttRunner, SherpaOnnxTtsRunner


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
            observed["init_count"] = int(observed.get("init_count", 0)) + 1
            observed["model_path"] = model_path

        def transcribe_without_streaming(self, audio_data, sample_rate: int = 16000):
            observed["sample_rate"] = sample_rate
            observed["audio_count"] = len(audio_data)
            return SimpleNamespace(lines=[SimpleNamespace(text="private moonshine transcript", start=0.0, end=0.1)])

        def close(self) -> None:
            observed["closed"] = True

    runner = MoonshineSttRunner(asset_manager=manager, audio_refs=audio_refs, transcriber_factory=FakeTranscriber)
    result = runner(TranscriptionRequest(trace_id="trace-moonshine", audio_ref_id=audio_ref.audio_ref_id, duration_ms=100, backend_id="moonshine-v2"), asset)
    result2 = runner(TranscriptionRequest(trace_id="trace-moonshine-2", audio_ref_id=audio_ref.audio_ref_id, duration_ms=100, backend_id="moonshine-v2"), asset)
    serialized = json.dumps(result.safe_projection()).lower()

    assert result.status == "succeeded"
    assert result2.status == "succeeded"
    assert result.text == "private moonshine transcript"
    assert str(observed["model_path"]).endswith("stt\\moonshine-v2") or str(observed["model_path"]).endswith("stt/moonshine-v2")
    assert observed["sample_rate"] == 16000
    assert observed["audio_count"] == 2
    assert observed["init_count"] == 1
    assert observed.get("closed") is None
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


def test_sherpa_onnx_stt_runner_transcribes_via_offline_recognizer(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="sherpa-onnx-asr", backend_id="sherpa-onnx-asr", model_kind="stt", relative_path="stt/sherpa-onnx-asr")
    audio_refs = VoiceWorkerAudioRefStore()
    audio_ref = audio_refs.remember_frames(trace_id="trace-sherpa-stt", frames=(AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),))
    observed: dict[str, object] = {}

    class FakeStream:
        result = SimpleNamespace(text="sherpa stt transcript")

        def accept_waveform(self, sample_rate: int, waveform: list[float]) -> None:
            observed["sample_rate"] = sample_rate
            observed["waveform_count"] = len(waveform)

    class FakeRecognizer:
        def __init__(self, model_dir: str) -> None:
            observed["model_dir"] = model_dir

        def create_stream(self) -> FakeStream:
            return FakeStream()

        def decode_stream(self, stream: FakeStream) -> None:
            observed["decoded"] = True

    runner = SherpaOnnxSttRunner(asset_manager=manager, audio_refs=audio_refs, recognizer_factory=FakeRecognizer)
    result = runner(TranscriptionRequest(trace_id="trace-sherpa-stt", audio_ref_id=audio_ref.audio_ref_id, duration_ms=100, backend_id="sherpa-onnx-asr"), asset)
    serialized = json.dumps(result.safe_projection()).lower()

    assert result.status == "succeeded"
    assert result.text == "sherpa stt transcript"
    assert str(observed["model_dir"]).endswith("stt\\sherpa-onnx-asr") or str(observed["model_dir"]).endswith("stt/sherpa-onnx-asr")
    assert observed["sample_rate"] == 16_000
    assert observed["decoded"] is True
    assert "sherpa stt transcript" not in serialized


def test_sherpa_onnx_tts_runner_synthesizes_via_offline_tts(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset_dir = manager.asset_root / "tts" / "sherpa-onnx-tts"
    asset_dir.mkdir(parents=True)
    asset = manager.install_local(VoiceModelInstallRequest(model_id="sherpa-onnx-tts", backend_id="sherpa-onnx-tts", model_kind="tts_voice", relative_path="tts/sherpa-onnx-tts", explicit_user_triggered=True))
    generated_audio = VoiceWorkerGeneratedAudioSink()
    observed: dict[str, object] = {}

    class FakeTts:
        def __init__(self, model_dir: str) -> None:
            observed["model_dir"] = model_dir

        def generate(self, text: str, sid: int = 0, speed: float = 1.0) -> SimpleNamespace:
            observed["text"] = text
            observed["sid"] = sid
            return SimpleNamespace(samples=[0.5, -0.5, 0.25], sample_rate=22_050)

    runner = SherpaOnnxTtsRunner(asset_manager=manager, generated_audio=generated_audio, tts_factory=FakeTts)
    result = runner(SpeechSynthesisRequest(trace_id="trace-sherpa-tts", text="  sherpa   tts  text  ", voice_id="sherpa-voice", backend_id="sherpa-onnx-tts"), asset)
    serialized = json.dumps(result.safe_projection()).lower()

    assert result.status == "succeeded"
    assert result.sample_rate == 22_050
    assert result.audio_ref == "memory://voice/generated/trace-sherpa-tts/sherpa-voice"
    assert generated_audio.resolve(result.audio_ref) != b""
    assert observed["text"] == "sherpa tts text"
    assert observed["sid"] == 0
    assert "sherpa tts text" not in serialized


def test_sherpa_onnx_kws_runner_detects_wakeword(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="kws/hey-marvex")
    frames = (AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),)
    observed: dict[str, object] = {}

    class FakeKwsStream:
        result = SimpleNamespace(keyword="hey marvex", confidence=0.91)

        def accept_waveform(self, sample_rate: int, waveform: list[float]) -> None:
            observed["sample_rate"] = sample_rate

    class FakeKws:
        def __init__(self, model_dir: str) -> None:
            observed["model_dir"] = model_dir

        def create_stream(self) -> FakeKwsStream:
            return FakeKwsStream()

        def decode_stream(self, stream: FakeKwsStream) -> None:
            observed["decoded"] = True

    runner = SherpaOnnxKwsRunner(asset_manager=manager, kws_factory=FakeKws)
    result = runner(frames, asset, phrase="Hey Marvex", threshold=0.72)

    assert result.detected is True
    assert result.confidence == 0.91
    assert result.backend_id == "sherpa-onnx-kws"
    assert observed["sample_rate"] == 16_000
    assert observed["decoded"] is True


def test_sherpa_onnx_kws_runner_returns_not_detected_when_no_keyword(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="kws/hey-marvex")
    frames = (AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),)

    class FakeKwsStream:
        result = SimpleNamespace(keyword="", confidence=0.1)

        def accept_waveform(self, sample_rate: int, waveform: list[float]) -> None:
            pass

    class FakeKws:
        def __init__(self, model_dir: str) -> None:
            pass

        def create_stream(self) -> FakeKwsStream:
            return FakeKwsStream()

        def decode_stream(self, stream: FakeKwsStream) -> None:
            pass

    runner = SherpaOnnxKwsRunner(asset_manager=manager, kws_factory=FakeKws)
    result = runner(frames, asset, phrase="Hey Marvex", threshold=0.72)

    assert result.detected is False
    assert result.reason_code == "wakeword.not_detected"


def test_sherpa_onnx_kws_runner_uses_get_result_when_available(tmp_path: Path) -> None:
    """Real sherpa-onnx 1.13.2 exposes KeywordSpotter.get_result(stream) which
    returns the detected keyword string; OnlineStream has no .result attribute.
    The runner must call get_result and not touch stream.result."""

    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="kws/hey-marvex")
    frames = (AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),)

    class RealishStream:
        # Deliberately raises if anyone touches .result, mirroring the
        # AttributeError seen in the field on sherpa-onnx 1.13.2.
        @property
        def result(self):  # noqa: D401 - test guard
            raise AttributeError("'OnlineStream' object has no attribute 'result'")

        def accept_waveform(self, sample_rate: int, waveform: list[float]) -> None:
            pass

    class RealishKws:
        def __init__(self, model_dir: str) -> None:
            pass

        def create_stream(self) -> RealishStream:
            return RealishStream()

        def is_ready(self, stream: RealishStream) -> bool:
            return False

        def decode_stream(self, stream: RealishStream) -> None:
            pass

        def get_result(self, stream: RealishStream) -> str:
            return "hey marvex"

        def reset_stream(self, stream: RealishStream) -> None:
            pass

    runner = SherpaOnnxKwsRunner(asset_manager=manager, kws_factory=RealishKws)
    result = runner(frames, asset, phrase="Hey Marvex", threshold=0.72)

    assert result.detected is True
    assert result.confidence == 0.72
    assert result.backend_id == "sherpa-onnx-kws"


def test_sherpa_onnx_kws_runner_get_result_empty_string_is_not_detected(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    asset = _install(manager, model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="kws/hey-marvex")
    frames = (AudioFrame(frame_id="f1", pcm=b"\x00\x00\x00@", sample_rate=16_000, channel_count=1, duration_ms=100),)

    class RealishKws:
        def __init__(self, model_dir: str) -> None:
            pass

        def create_stream(self):
            return SimpleNamespace(accept_waveform=lambda *a, **k: None)

        def is_ready(self, stream) -> bool:
            return False

        def decode_stream(self, stream) -> None:
            pass

        def get_result(self, stream) -> str:
            return ""

    runner = SherpaOnnxKwsRunner(asset_manager=manager, kws_factory=RealishKws)
    result = runner(frames, asset, phrase="Hey Marvex", threshold=0.72)

    assert result.detected is False
    assert result.reason_code == "wakeword.not_detected"


def test_normalized_keywords_use_boost_colon_threshold_hash_order(tmp_path: Path) -> None:
    # Regression: the sherpa-onnx keyword format is ":BOOST #THRESHOLD". An
    # earlier fix inverted it (":0.2 #2.0" => threshold 2.0) and the wake word
    # could never fire. Verify we emit a high boost + low threshold.
    from packages.voice_worker_runtime.model_adapters import _normalized_kws_keywords_file

    tokens = tmp_path / "tokens.txt"
    vocab = ["<blk>", "▁HE", "Y", "▁MAR", "VE", "X"]
    tokens.write_text("\n".join(f"{tok} {i}" for i, tok in enumerate(vocab)), encoding="utf-8")
    keywords = tmp_path / "keywords.txt"
    keywords.write_text("▁HE Y ▁MAR VE X :1.5 #0.2 @HEY_MARVEX\n", encoding="utf-8")

    out = _normalized_kws_keywords_file(tokens=tokens, keywords=keywords)
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert ":2.0" in text  # boost
    assert "#0.1" in text  # threshold (low for recall on real voice)
    assert "#2.0" not in text  # never a 2.0 threshold (the inverted-order bug)
    assert "@HEY_MARVEX" in text


def test_generate_keywords_from_phrase_returns_none_without_tokenizer(tmp_path: Path) -> None:
    from packages.voice_worker_runtime.model_adapters import _generate_kws_keywords_file

    tokens = tmp_path / "tokens.txt"
    tokens.write_text("<blk> 0\n", encoding="utf-8")
    # No bpe.model and no en.phone under model_root -> no usable tokenizer.
    assert _generate_kws_keywords_file(tokens=tokens, model_root=tmp_path, phrase="Hey Marvex") is None


def test_generate_keywords_phoneme_model_uses_en_phone_lexicon(tmp_path: Path) -> None:
    from packages.voice_worker_runtime.model_adapters import _generate_kws_keywords_file

    phones = ["HH", "EY1", "M", "AA1", "R", "V", "EH1", "K", "S"]
    (tmp_path / "tokens.txt").write_text(
        "\n".join(f"{p} {i}" for i, p in enumerate(["<blk>", *phones])), encoding="utf-8"
    )
    # en.phone provides HEY; MARVEX comes from the coined-phoneme table.
    (tmp_path / "en.phone").write_text("HEY HH EY1\n", encoding="utf-8")
    out = _generate_kws_keywords_file(tokens=tmp_path / "tokens.txt", model_root=tmp_path, phrase="Hey Marvex")
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "HH EY1 M AA1 R V EH1 K S" in text
    assert ":2.0 #0.1" in text
    assert "@HEY_MARVEX" in text
