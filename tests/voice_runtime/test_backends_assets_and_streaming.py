from __future__ import annotations

import json

from packages.voice_runtime import (
    BargeInDetector,
    BargeInPolicy,
    ChunkPlaybackState,
    DeterministicSttAdapter,
    DeterministicTtsAdapter,
    EarlySpeechPolicy,
    EarlySpeechTrigger,
    SentenceBoundaryDetector,
    SentenceClampPolicy,
    SpeechSynthesisRequest,
    STTModelRegistry,
    StreamingTextChunk,
    TTSQueue,
    TTSVoiceRegistry,
    TranscriptionRequest,
    UserSpeechDuringPlaybackEvent,
    VoiceDownloadRequest,
    VoiceInstallStatus,
    VoiceModelManifest,
    VoiceModelRef,
    VoicePersonalityProfile,
    VoiceRuntimeConfig,
    VoiceTestRequest,
    VoiceTestResult,
    WakeWordModelRegistry,
    build_default_voice_backend_registry,
    select_early_speech,
)


def test_backend_registry_selects_main_fallback_manual_and_auto_fallback() -> None:
    registry = build_default_voice_backend_registry(
        stt_backends=(DeterministicSttAdapter("moonshine-v2", text="hello"), DeterministicSttAdapter("sensevoice-small", text="fallback")),
        tts_backends=(DeterministicTtsAdapter("kokoro-onnx"), DeterministicTtsAdapter("piper-tts")),
    )

    stt = registry.select_stt("main")
    fallback = registry.select_stt("fallback")
    manual = registry.select_tts("piper-tts")

    assert stt.backend_id == "moonshine-v2"
    assert fallback.backend_id == "sensevoice-small"
    assert manual.backend_id == "piper-tts"
    assert registry.safe_projection()["stt_switchable"] is True
    assert registry.safe_projection()["tts_switchable"] is True


def test_stt_and_tts_results_are_safe_and_backend_attributed() -> None:
    stt = DeterministicSttAdapter("moonshine-v2", text="turn on the lights")
    tts = DeterministicTtsAdapter("kokoro-onnx")

    transcription = stt.transcribe(TranscriptionRequest(trace_id="trace-1", audio_ref_id="audio-1", duration_ms=320))
    synthesis = tts.synthesize(SpeechSynthesisRequest(trace_id="trace-1", text="I am checking that.", voice_id="af_heart"))

    assert transcription.text == "turn on the lights"
    assert transcription.backend_id == "moonshine-v2"
    assert synthesis.backend_id == "kokoro-onnx"
    assert synthesis.voice_id == "af_heart"
    assert synthesis.raw_audio_persisted is False
    assert "I am checking" not in json.dumps(synthesis.safe_projection())


def test_voice_model_registries_install_remove_download_and_test_without_internals() -> None:
    stt_models = STTModelRegistry()
    tts_voices = TTSVoiceRegistry()
    wakeword_models = WakeWordModelRegistry()
    manifest = VoiceModelManifest(
        model=VoiceModelRef(model_id="moonshine-v2-base", backend_id="moonshine-v2", model_kind="stt"),
        install_status=VoiceInstallStatus.INSTALLED,
        local_uri="local://models/stt/moonshine-v2-base",
    )

    stt_models.install(manifest)
    tts_voices.install(manifest.model_copy(update={"model": VoiceModelRef(model_id="af_heart", backend_id="kokoro-onnx", model_kind="tts_voice")}))
    wakeword_models.install(manifest.model_copy(update={"model": VoiceModelRef(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword")}))
    download = stt_models.download(VoiceDownloadRequest(model_id="moonshine-v2-base", backend_id="moonshine-v2", model_kind="stt", source_uri="local://bundled/moonshine"))
    test = VoiceTestResult.from_request(VoiceTestRequest(test_id="test-tts", backend_id="kokoro-onnx", phrase="Testing voice."), status="passed")

    assert download.status == VoiceInstallStatus.INSTALLED
    assert stt_models.list_installed()[0].model.model_id == "moonshine-v2-base"
    assert tts_voices.list_installed()[0].model.model_kind == "tts_voice"
    assert wakeword_models.list_installed()[0].model.backend_id == "sherpa-onnx-kws"
    assert test.raw_audio_persisted is False
    assert "bundled" not in json.dumps(stt_models.safe_projection()).lower()
    assert stt_models.remove("moonshine-v2-base").removed is True


def test_sentence_clamper_and_tts_queue_cut_on_safe_boundaries() -> None:
    detector = SentenceBoundaryDetector(SentenceClampPolicy(max_chars=48))
    chunks = [StreamingTextChunk(text="I am checking that", index=0), StreamingTextChunk(text=". Search is next", index=1)]
    ready = [item for chunk in chunks for item in detector.accept(chunk)]
    queue = TTSQueue()

    for item in ready:
        queue.enqueue(item)

    assert [item.text for item in ready] == ["I am checking that."]
    assert queue.pending_count == 1
    assert queue.cancel_all(reason_code="barge_in").canceled_count == 1


def test_barge_in_interrupts_playback_and_preserves_safe_trace_state() -> None:
    detector = BargeInDetector(BargeInPolicy(enabled=True, vad_confidence_threshold=0.6))
    event = UserSpeechDuringPlaybackEvent(trace_id="trace-1", confidence=0.88, playback_chunk_id="chunk-1")
    state = ChunkPlaybackState.playing(chunk_id="chunk-1", backend_id="kokoro-onnx")

    result = detector.evaluate(event, state)

    assert result.interrupted is True
    assert result.reason_code == "barge_in.user_speech_detected"
    assert result.cancel_state.queued_chunks_canceled is True
    assert result.safe_projection()["raw_audio_persisted"] is False


def test_early_speech_is_rate_limited_and_never_claims_unknown_facts() -> None:
    policy = EarlySpeechPolicy(enabled=True, min_interval_ms=10_000)
    first = select_early_speech(EarlySpeechTrigger(intent_kind="web_search", elapsed_ms=900), policy=policy)
    second = select_early_speech(EarlySpeechTrigger(intent_kind="web_search", elapsed_ms=1_000, previous_filler_elapsed_ms=500), policy=policy)

    assert first.should_speak is True
    assert first.text == "I am searching for the latest information."
    assert first.claims_facts_without_evidence is False
    assert second.should_speak is False


def test_voice_personality_safe_projection_controls_pacing_voice_and_sensitive_content() -> None:
    profile = VoicePersonalityProfile.default().model_copy(update={"active_voice_id": "af_heart"})
    projection = profile.safe_projection()

    assert projection["active_voice_id"] == "af_heart"
    assert projection["auto_speak_enabled"] is True
    assert projection["sensitive_content_policy"] == "ask"
    assert VoiceRuntimeConfig.default().personality.filler_frequency.value == "medium"
