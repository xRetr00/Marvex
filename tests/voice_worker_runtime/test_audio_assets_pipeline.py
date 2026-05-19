from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from packages.voice_runtime import DeterministicSttAdapter, DeterministicTtsAdapter, VoicePolicyDecision, VoiceRuntime
from packages.voice_worker_runtime import (
    FakeLocalAudioAdapter,
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

    installed = manager.install_local(
        VoiceModelInstallRequest(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt", relative_path="stt/moonshine-v2", explicit_user_triggered=True)
    )
    blocked = manager.install_local(
        VoiceModelInstallRequest(model_id="escape", backend_id="moonshine-v2", model_kind="stt", relative_path="../escape", explicit_user_triggered=True)
    )

    assert installed.status == "installed"
    assert installed.local_path_present is True
    assert blocked.status == "blocked"
    assert blocked.exact_blocker == "model_path_outside_voice_asset_root"
    assert manager.registry().installed_count == 1


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


def test_worker_barge_in_interrupts_playback_and_routes_new_user_speech_event() -> None:
    controller = VoiceWorkerController(config=VoiceWorkerConfig.default(), audio=FakeLocalAudioAdapter())
    controller.handle(VoiceWorkerCommand(command="start", command_id="cmd-start"))

    result = controller.handle(VoiceWorkerCommand(command="test_playback", command_id="cmd-playback", payload={"simulate_barge_in": True}))

    assert result.event.event_type == VoiceWorkerEventType.BARGE_IN_DETECTED
    assert result.status.playback_status == "interrupted"
    assert result.status.safe_projection()["queued_tts_count"] == 0


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
    assert playing.status == "playing"
    assert interrupted.status == "interrupted"
    assert [call[0] for call in calls] == ["rec", "wait", "rec", "wait", "play", "stop"]
