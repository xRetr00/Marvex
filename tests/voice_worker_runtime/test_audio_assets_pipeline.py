# file size justification: comprehensive integration tests for the voice worker
# audio pipeline — fake and real audio adapters, PCM playback, model downloads,
# full turn cycles, telemetry, barge-in, and sounddevice wiring.
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import UTC, datetime

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.assistant_turn_integration import EndToEndTurnStateStore, run_end_to_end_assistant_turn
from packages.contracts import TraceStage
from packages.voice_runtime import AudioFrame, DeterministicSttAdapter, DeterministicTtsAdapter, SpeechSynthesisResult, TranscriptionResult, VADDecision, VoicePolicyDecision, VoiceRuntime, WakeWordDetectionResult
from packages.voice_worker_runtime import (
    VoiceWorkerBackendRuntime,
    FakeLocalAudioAdapter,
    SoundDeviceAudioAdapter,
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
    VoiceWorkerEventType,
)


def test_fake_audio_adapter_lists_devices_tests_mic_and_captures_pcm_frames_without_persistence() -> None:
    adapter = FakeLocalAudioAdapter()

    inputs = adapter.list_input_devices()
    outputs = adapter.list_output_devices()
    level = adapter.test_mic_level(device_id=inputs[0].device_id, duration_ms=100)
    frames = tuple(adapter.capture_frames(device_id=inputs[0].device_id, sample_rate=16_000, channel_count=1, frame_count=2))

    assert inputs[0].is_input is True
    assert outputs[0].is_output is True
    assert level.status == "passed"
    assert level.peak_level > 0
    assert len(frames) == 2
    assert all(frame.safe_projection()["raw_audio_persisted"] is False for frame in frames)
    assert frames[0].safe_projection()["byte_count"] > 0


def test_playback_can_start_stop_and_interrupt_without_generated_audio_persistence() -> None:
    adapter = FakeLocalAudioAdapter()
    output = adapter.list_output_devices()[0]

    playing = adapter.play_audio(device_id=output.device_id, audio_ref="memory://voice/generated/test", sample_rate=24_000)
    interrupted = adapter.interrupt_playback(reason_code="barge_in.user_speech_detected")
    stopped = adapter.stop_playback()

    assert playing.status == "playing"
    assert playing.raw_audio_persisted is False
    assert interrupted.status == "interrupted"
    assert interrupted.reason_code == "barge_in.user_speech_detected"
    assert stopped.status == "stopped"


def test_asset_manager_rejects_path_traversal_and_installs_only_under_safe_asset_root(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    installed_path = tmp_path / "voice-assets" / "stt" / "moonshine-v2"
    installed_path.mkdir(parents=True)

    installed = manager.install_local(
        VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True)
    )
    missing = manager.install_local(
        VoiceModelInstallRequest(model_id="missing", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/missing", explicit_user_triggered=True)
    )
    blocked = manager.install_local(
        VoiceModelInstallRequest(model_id="escape", backend_id="moonshine-v2", model_kind="stt", relative_path="../escape", explicit_user_triggered=True)
    )

    assert installed.status == "installed"
    assert installed.local_path_present is True
    assert missing.status == "not_installed"
    assert missing.exact_blocker == "model_path_not_found_under_voice_asset_root"
    assert blocked.status == "blocked"
    assert blocked.exact_blocker == "model_path_outside_voice_asset_root"
    assert manager.registry().installed_count == 1


def test_asset_manager_reports_required_backend_assets_without_raw_paths(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex", checksum_sha256="sha256-test", explicit_user_triggered=True)
    )

    registry = manager.registry()
    serialized = registry.model_dump(mode="json")

    statuses = {item.model_id: item for item in registry.installed}
    assert statuses["hey-marvex"].status == "installed"
    assert statuses["hey-marvex"].checksum_present is True
    assert str(tmp_path).lower() not in str(serialized).lower()
    assert registry.required_ready_count == 1
    assert registry.required_blocked_count >= 3


def test_asset_manager_blocks_checksum_mismatch_for_file_assets(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    target = tmp_path / "voice-assets" / "wakeword" / "hey-marvex.kws"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"hey marvex model bytes")
    expected_hash = hashlib.sha256(b"different bytes").hexdigest()

    result = manager.install_local(
        VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex.kws", checksum_sha256=expected_hash, explicit_user_triggered=True)
    )

    assert result.status == "blocked"
    assert result.local_path_present is True
    assert result.checksum_present is True
    assert result.exact_blocker == "model_asset_checksum_mismatch"
    assert manager.registry().installed_count == 0


def test_worker_full_manual_voice_turn_uses_vad_stt_policy_tts_playback_and_events() -> None:
    voice_runtime = VoiceRuntime.with_deterministic_backends(stt=DeterministicSttAdapter("moonshine-v2", text="status please"), tts=DeterministicTtsAdapter("kokoro-onnx"))
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter(), voice_runtime=voice_runtime)
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    result = controller.run_manual_turn(
        trace_id="trace-worker-turn",
        assistant_turn_runner=lambda transcript: {"text": f"Voice answer for {transcript}"},
        policy_decider=lambda transcript: VoicePolicyDecision.allow(trace_id="trace-worker-turn", reason_code="policy.voice.safe"),
    )

    assert result.turn.status == "completed"
    assert [event.event_type for event in result.events] == [
        VoiceWorkerEventType.VAD_SPEECH_STARTED,
        VoiceWorkerEventType.VAD_SPEECH_ENDED,
        VoiceWorkerEventType.TRANSCRIPTION_STARTED,
        VoiceWorkerEventType.TRANSCRIPTION_COMPLETED,
        VoiceWorkerEventType.ASSISTANT_TURN_STARTED,
        VoiceWorkerEventType.TTS_STARTED,
        VoiceWorkerEventType.PLAYBACK_STARTED,
        VoiceWorkerEventType.PLAYBACK_FINISHED,
    ]
    assert result.playback.status == "completed"
    assert result.safe_projection()["raw_audio_persisted"] is False
    telemetry = controller.status().safe_projection()["telemetry_summary"]
    assert telemetry["event_count"] >= 9
    assert telemetry["event_counts"]["vad_speech_started"] == 1
    assert telemetry["event_counts"]["transcription_completed"] == 1
    assert telemetry["event_counts"]["playback_finished"] == 1
    assert telemetry["raw_audio_persisted"] is False
    assert telemetry["raw_transcript_persisted"] is False


def test_worker_manual_voice_turn_tracks_preroll_tail_transcript_and_early_speech() -> None:
    voice_runtime = VoiceRuntime.with_deterministic_backends(stt=DeterministicSttAdapter("moonshine-v2", text="search local docs"), tts=DeterministicTtsAdapter("kokoro-onnx"))
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter(), voice_runtime=voice_runtime)
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    result = controller.run_manual_turn(
        trace_id="trace-worker-early-speech",
        assistant_turn_runner=lambda transcript: {"text": f"Voice answer for {transcript}"},
        policy_decider=lambda transcript: VoicePolicyDecision.allow(trace_id="trace-worker-early-speech", reason_code="policy.voice.safe"),
    )
    projection = result.safe_projection()

    assert projection["pre_roll_ms"] == 400
    assert projection["tail_padding_ms"] == 240
    assert projection["partial_transcript_count"] == 1
    assert projection["final_transcript_event"] is True
    assert projection["early_speech"]["should_speak"] is True
    assert projection["early_speech"]["claims_facts_without_evidence"] is False
    assert projection["max_utterance_ms"] == 30000


def test_worker_live_capture_cycle_segments_speech_with_preroll_tail_and_silence_cutoff() -> None:
    class ScriptedAudio(FakeLocalAudioAdapter):
        def capture_frames(self, *, device_id: str | None, sample_rate: int, channel_count: int, frame_count: int):
            del device_id, frame_count
            for index in range(8):
                yield AudioFrame(frame_id=f"scripted-{index}", pcm=b"\x01\x00" * 160, sample_rate=sample_rate, channel_count=channel_count, duration_ms=100)

    decisions = [False, False, True, True, True, False, False, False]
    config = VoiceWorkerConfig.default().model_copy(update={"vad": VoiceWorkerConfig.default().vad.model_copy(update={"silence_timeout_ms": 300})})
    voice_runtime = VoiceRuntime.with_deterministic_backends(stt=DeterministicSttAdapter("moonshine-v2", text="open calendar"), tts=DeterministicTtsAdapter("kokoro-onnx"))
    controller = VoiceWorkerController(config=config, audio=ScriptedAudio(), voice_runtime=voice_runtime)
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    result = controller.run_live_capture_cycle(
        trace_id="trace-live-cycle",
        trigger="manual",
        max_frame_count=8,
        vad_decider=lambda frame, index: VADDecision.speech_started(frame_count=1, confidence=0.9, noise_floor_db=-42) if decisions[index] else VADDecision.silence(frame_count=1, confidence=0.1, noise_floor_db=-50),
        assistant_turn_runner=lambda transcript: {"text": f"Voice answer for {transcript}"},
        policy_decider=lambda transcript: VoicePolicyDecision.allow(trace_id="trace-live-cycle", reason_code="policy.voice.safe"),
    )
    projection = result.safe_projection()

    assert result.turn.status == "completed"
    assert projection["trigger"] == "manual"
    assert projection["captured_frame_count"] == 8
    assert projection["speech_frame_count"] == 3
    assert projection["pre_roll_ms"] == 200
    assert projection["tail_padding_ms"] == 240
    assert projection["segment_finalized_reason"] == "chunk.finalized.silence_cutoff"
    assert projection["prevents_runaway_recording"] is True
    assert projection["raw_audio_persisted"] is False
    assert projection["raw_transcript_persisted"] is False
    assert [event.event_type for event in result.events].count(VoiceWorkerEventType.VAD_SPEECH_STARTED) == 1
    assert [event.event_type for event in result.events].count(VoiceWorkerEventType.VAD_SPEECH_ENDED) == 1


def test_worker_live_capture_cycle_stops_at_max_utterance_without_assistant_dispatch() -> None:
    config = VoiceWorkerConfig.default().model_copy(update={"vad": VoiceWorkerConfig.default().vad.model_copy(update={"max_utterance_ms": 300})})
    controller = VoiceWorkerController(config=config, audio=FakeLocalAudioAdapter(), voice_runtime=VoiceRuntime.with_deterministic_backends(stt=DeterministicSttAdapter("moonshine-v2", text="should not dispatch"), tts=DeterministicTtsAdapter("kokoro-onnx")))
    dispatches: list[str] = []

    result = controller.run_live_capture_cycle(
        trace_id="trace-live-runaway",
        trigger="manual",
        max_frame_count=8,
        vad_decider=lambda frame, index: VADDecision.speech_started(frame_count=1, confidence=0.9, noise_floor_db=-42),
        assistant_turn_runner=lambda transcript: dispatches.append(transcript) or {"text": "unexpected"},
        policy_decider=lambda transcript: VoicePolicyDecision.allow(trace_id="trace-live-runaway", reason_code="policy.voice.safe"),
    )
    projection = result.safe_projection()

    assert result.turn is None
    assert dispatches == []
    assert projection["segment_finalized_reason"] == "chunk.finalized.max_utterance_duration"
    assert projection["assistant_dispatch_started"] is False
    assert projection["prevents_runaway_recording"] is True
    assert projection["captured_frame_count"] == 3


def test_worker_manual_voice_turn_can_dispatch_transcript_to_assistant_turn_spine() -> None:
    store = EndToEndTurnStateStore()
    voice_runtime = VoiceRuntime.with_deterministic_backends(stt=DeterministicSttAdapter("moonshine-v2", text="calculate 2 plus 2"), tts=DeterministicTtsAdapter("kokoro-onnx"))
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter(), voice_runtime=voice_runtime)

    def assistant_turn_runner(transcript: str):
        event = build_text_input_event(schema_version="1", trace_id="trace-worker-e2e", event_id="input-worker-e2e", text=transcript, timestamp=datetime(2026, 5, 19, 12, 0, tzinfo=UTC), session_id="session-worker-e2e")
        turn_input = build_turn_input_from_event(schema_version="1", trace_id="trace-worker-e2e", turn_id="turn-worker-e2e", input_event=event)
        return run_end_to_end_assistant_turn(turn_input, model="fake-model", state_store=store).assistant_result

    result = controller.run_manual_turn(
        trace_id="trace-worker-e2e",
        assistant_turn_runner=assistant_turn_runner,
        policy_decider=lambda transcript: VoicePolicyDecision.allow(trace_id="trace-worker-e2e", reason_code="policy.voice.safe"),
    )

    trace = store.trace_reader.read_trace("trace-worker-e2e")
    assert result.turn.status == "completed"
    assert result.turn.policy_decision.execution_started is False
    assert trace is not None
    assert {event["stage"] for event in trace["events"]} >= {TraceStage.TURN_RECEIVED.value, TraceStage.TURN_COMPLETED.value}
    assert "calculate 2 plus 2" not in str(result.safe_projection()).lower()


def test_worker_barge_in_interrupts_playback_and_routes_new_user_speech_event() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter())
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    result = controller.handle(VoiceWorkerCommand(command="test_playback", command_id="cmd-playback", payload={"simulate_barge_in": True}))

    assert result.event.event_type == VoiceWorkerEventType.BARGE_IN_DETECTED
    assert result.status.playback_status == "interrupted"
    assert result.status.safe_projection()["queued_tts_count"] == 0


def test_worker_wakeword_test_requires_enabled_policy_and_installed_asset(tmp_path: Path) -> None:
    from packages.voice_runtime import WakeWordDetectionResult

    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    # Inject a fake wakeword_runner so the test is independent of whether
    # sherpa-onnx is actually installed in the test environment.
    def _fake_kws_runner(frames, asset, *, phrase, threshold):
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=0.95, backend_id=asset.backend_id)

    backend = VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=_fake_kws_runner)
    _disabled_cfg = VoiceWorkerConfig.default().model_copy(update={"wakeword": VoiceWorkerConfig.default().wakeword.model_copy(update={"enabled": False})})
    controller = VoiceWorkerController(config=_disabled_cfg, audio=FakeLocalAudioAdapter(), asset_manager=manager, backend_runtime=backend)

    disabled = controller.handle(VoiceWorkerCommand(command="test_wakeword", command_id="cmd-wake-disabled"))
    controller.handle(VoiceWorkerCommand(command="reload_config", command_id="cmd-reload", payload={"wakeword_enabled": True}))
    missing_asset = controller.handle(VoiceWorkerCommand(command="test_wakeword", command_id="cmd-wake-missing"))
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex", explicit_user_triggered=True))
    ready = controller.handle(VoiceWorkerCommand(command="test_wakeword", command_id="cmd-wake-ready"))

    assert disabled.event.event_type == VoiceWorkerEventType.ERROR
    assert disabled.error and disabled.error.reason_code == "wakeword_not_enabled"
    assert missing_asset.event.event_type == VoiceWorkerEventType.ERROR
    assert missing_asset.error and missing_asset.error.reason_code == "wakeword_model_not_installed"
    assert ready.event.event_type == VoiceWorkerEventType.WAKEWORD_DETECTED
    assert ready.error is None


def test_worker_backend_runtime_blocks_missing_stt_asset_before_runner(tmp_path: Path) -> None:
    calls: list[str] = []
    runtime = VoiceWorkerBackendRuntime(
        asset_manager=VoiceAssetManager(asset_root=tmp_path / "voice-assets"),
        stt_runner=lambda request, asset: calls.append(asset.model_id) or TranscriptionResult.succeeded(
            trace_id=request.trace_id,
            text="should not run",
            backend_id=request.backend_id or "moonshine-v2",
            duration_ms=request.duration_ms,
        ),
    )

    result = runtime.test_stt(trace_id="trace-missing-stt", backend_id="moonshine-v2", audio_ref_id="memory://voice/test/stt")

    assert result.status == "failed"
    assert result.safe_error is not None
    assert result.safe_error.details["reason_code"] == "model_asset_missing_manual_install_required"
    assert calls == []
    assert result.raw_audio_persisted is False
    assert "should not run" not in json.dumps(result.safe_projection()).lower()


def test_worker_test_stt_invokes_installed_asset_runner_without_rendering_transcript(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True))
    calls: list[tuple[str, str]] = []

    def stt_runner(request, asset):
        calls.append((request.audio_ref_id, asset.model_id))
        return TranscriptionResult.succeeded(trace_id=request.trace_id, text="private transcript", backend_id=request.backend_id or "moonshine-v2", duration_ms=request.duration_ms, language="en", confidence=0.91)

    controller = VoiceWorkerController(asset_manager=manager, backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, stt_runner=stt_runner))

    result = controller.handle(VoiceWorkerCommand(command="test_stt", command_id="cmd-stt", payload={"audio_ref_id": "memory://voice/test/stt"}))
    serialized = json.dumps(result.safe_projection()).lower()

    assert calls == [("memory://voice/test/stt", "moonshine-v2")]
    assert result.event.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED
    assert result.event.summary["status"] == "succeeded"
    assert result.event.summary["text_present"] is True
    assert "private transcript" not in serialized
    assert result.status.stt_backend_status["status"] == "ready"


def test_worker_test_tts_invokes_installed_voice_runner_without_rendering_text(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "tts" / "kokoro-af-heart").mkdir(parents=True)
    (tmp_path / "voice-assets" / "tts" / "kokoro-voices").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="kokoro-af-heart", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-af-heart", explicit_user_triggered=True))
    manager.install_local(VoiceModelInstallRequest(model_id="kokoro-voices", backend_id="kokoro-onnx", model_kind="tts_voice", relative_path="tts/kokoro-voices", explicit_user_triggered=True))
    calls: list[tuple[str, str]] = []

    def tts_runner(request, asset):
        calls.append((request.text, asset.model_id))
        return SpeechSynthesisResult.succeeded(trace_id=request.trace_id, audio_ref="memory://voice/generated/cmd-tts/af_heart", backend_id=request.backend_id or "kokoro-onnx", voice_id=request.voice_id, duration_ms=180)

    controller = VoiceWorkerController(asset_manager=manager, backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, tts_runner=tts_runner))

    result = controller.handle(VoiceWorkerCommand(command="test_tts", command_id="cmd-tts", payload={"text": "sensitive spoken response"}))
    serialized = json.dumps(result.safe_projection()).lower()

    assert calls == [("sensitive spoken response", "kokoro-af-heart")]
    assert result.event.event_type == VoiceWorkerEventType.TTS_STARTED
    assert result.event.summary["status"] == "succeeded"
    assert result.event.summary["audio_ref_present"] is True
    assert "sensitive spoken response" not in serialized
    assert result.status.tts_backend_status["status"] == "ready"


def test_worker_wakeword_uses_installed_asset_runner_when_configured(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager.install_local(VoiceModelInstallRequest(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword", relative_path="wakeword/hey-marvex", explicit_user_triggered=True))
    calls: list[tuple[int, str]] = []

    def wakeword_runner(frames, asset, *, phrase: str, threshold: float):
        calls.append((len(frames), asset.model_id))
        return WakeWordDetectionResult.detected(phrase=phrase, confidence=threshold + 0.01, backend_id=asset.backend_id)

    config = VoiceWorkerConfig.default().model_copy(update={"wakeword": VoiceWorkerConfig.default().wakeword.model_copy(update={"enabled": True})})
    controller = VoiceWorkerController(config=config, audio=FakeLocalAudioAdapter(), asset_manager=manager, backend_runtime=VoiceWorkerBackendRuntime(asset_manager=manager, wakeword_runner=wakeword_runner))

    result = controller.handle(VoiceWorkerCommand(command="test_wakeword", command_id="cmd-wake-runner"))

    assert calls == [(4, "hey-marvex")]
    assert result.event.event_type == VoiceWorkerEventType.WAKEWORD_DETECTED
    assert result.event.summary["backend_id"] == "sherpa-onnx-kws"
    assert result.event.summary["wakeword_ready"] is True


def test_worker_status_projection_includes_health_events_errors_and_model_status(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter(), asset_manager=manager)
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))
    controller.handle(VoiceWorkerCommand(command="test_wakeword", command_id="cmd-wake"))

    projection = controller.status().safe_projection()

    assert projection["health"]["local_only"] is True
    assert projection["health"]["hidden_recording_allowed"] is False
    assert projection["recent_events"][0]["event_type"] == "mic_started"
    # Wakeword is enabled by default now, so a test with no installed KWS asset
    # surfaces the missing-asset blocker rather than the not-enabled one.
    assert projection["error"]["reason_code"] == "wakeword_model_not_installed"
    assert projection["model_assets"]["required_blocked_count"] >= 4
    assert projection["stt_backend_status"]["active_backend_id"] == "moonshine-v2"
    assert projection["stt_backend_status"]["status"] == "not_ready"
    assert projection["tts_backend_status"]["active_backend_id"] == "kokoro-onnx"
    assert projection["tts_backend_status"]["status"] == "not_ready"
    assert projection["wakeword_model_status"]["model_id"] == "hey-marvex"
    assert projection["wakeword_model_status"]["status"] == "not_installed"
    assert "raw_audio" not in str(projection).lower().replace("raw_audio_persisted", "")


def test_worker_status_projection_contains_safe_telemetry_counts_only(tmp_path: Path) -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter(), asset_manager=VoiceAssetManager(asset_root=tmp_path / "voice-assets"))
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))
    controller.handle(VoiceWorkerCommand(command="test_mic", command_id="cmd-mic"))
    controller.handle(VoiceWorkerCommand(command="test_playback", command_id="cmd-playback", payload={"simulate_barge_in": True}))

    telemetry = controller.status().safe_projection()["telemetry"]
    serialized = json.dumps(telemetry).lower()

    assert telemetry["worker_lifecycle_events"] == 1
    assert telemetry["mic_capture_events"] == 1
    assert telemetry["playback_events"] == 1
    assert telemetry["barge_in_events"] == 1
    assert telemetry["durations_counts_only"] is True
    assert "pcm" not in serialized
    assert "transcript" not in serialized.replace("raw_transcript_persisted", "")


def test_sounddevice_adapter_uses_real_runtime_api_shape(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class _FakeRecording:
        def __init__(self) -> None:
            self.size = 4

        def max(self) -> float:
            return 0.5

        def mean(self) -> float:
            return 0.25

        def tobytes(self) -> bytes:
            return b"\x01\x00\x02\x00"

    fake_sd = SimpleNamespace(
        query_devices=lambda: ({"name": "Mic", "max_input_channels": 1, "max_output_channels": 0, "default_samplerate": 16000}, {"name": "Speaker", "max_input_channels": 0, "max_output_channels": 2, "default_samplerate": 24000}),
        rec=lambda frames, samplerate, channels, dtype, device=None: calls.append(("rec", (frames, samplerate, channels, dtype, device))) or _FakeRecording(),
        wait=lambda: calls.append(("wait", True)),
        play=lambda data, samplerate, device=None: calls.append(("play", (data, samplerate, device))),
        stop=lambda: calls.append(("stop", True)),
    )
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    from packages.voice_worker_runtime import SoundDeviceAudioAdapter

    adapter = SoundDeviceAudioAdapter()
    assert adapter.list_input_devices()[0].label == "Mic"
    assert adapter.test_mic_level(device_id="0", duration_ms=100).peak_level == 0.5
    frames = tuple(adapter.capture_frames(device_id="0", sample_rate=16_000, channel_count=1, frame_count=1))
    playing = adapter.play_audio(device_id="1", audio_ref="memory://voice/generated/test", sample_rate=24_000)
    interrupted = adapter.interrupt_playback(reason_code="barge_in.user_speech_detected")

    assert frames[0].raw_audio_persisted is False
    assert frames[0].pcm == b"\x01\x00\x02\x00"
    # play_audio now blocks (sd.wait) and returns "completed" to signal the
    # audio finished playing before returning to the caller.
    assert playing.status == "completed"
    assert playing.reason_code == "sounddevice.playback_completed"
    assert interrupted.status == "interrupted"
    assert [call[0] for call in calls] == ["rec", "wait", "rec", "wait", "play", "wait", "stop"]


def test_sounddevice_adapter_play_audio_resolves_real_pcm_via_resolver(monkeypatch) -> None:
    played_data: list[object] = []
    fake_sd = __import__("types").SimpleNamespace(
        query_devices=lambda: (),
        play=lambda data, samplerate, device=None: played_data.append(data),
        wait=lambda: None,
        stop=lambda: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    from packages.voice_worker_runtime import SoundDeviceAudioAdapter

    # Build 2-byte int16 PCM: one sample at +1.0 (0x7FFF) and one at -1.0 (0x8001)
    import struct
    pcm = struct.pack("<hh", 32767, -32767)
    resolver: dict[str, bytes] = {"memory://voice/generated/t1/v1": pcm}
    adapter = SoundDeviceAudioAdapter(pcm_resolver=resolver.get)

    result = adapter.play_audio(device_id=None, audio_ref="memory://voice/generated/t1/v1", sample_rate=22_050)
    assert result.status == "completed"
    assert len(played_data) == 1
    samples = played_data[0]
    # Should be a list of floats derived from the PCM — not the raw bytes
    assert isinstance(samples, list)
    assert len(samples) == 2
    assert abs(samples[0] - (32767 / 32768.0)) < 0.01
    assert abs(samples[1] - (-32767 / 32768.0)) < 0.01


def test_sounddevice_adapter_plays_silence_fallback_when_no_resolver(monkeypatch) -> None:
    played_data: list[object] = []
    fake_sd = __import__("types").SimpleNamespace(
        query_devices=lambda: (),
        play=lambda data, samplerate, device=None: played_data.append(data),
        wait=lambda: None,
        stop=lambda: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", fake_sd)

    from packages.voice_worker_runtime import SoundDeviceAudioAdapter

    adapter = SoundDeviceAudioAdapter()  # no resolver
    result = adapter.play_audio(device_id=None, audio_ref="memory://voice/generated/unknown", sample_rate=16_000)
    assert result.status == "completed"
    assert len(played_data) == 1
    # Fallback: 50 ms of silence = 800 zeros at 16 kHz
    assert len(played_data[0]) >= 1
    assert all(s == 0.0 for s in played_data[0])
