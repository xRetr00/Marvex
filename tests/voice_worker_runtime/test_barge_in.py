"""Tests for barge-in during a spoken reply (docs/TODO/04).

While the assistant speaks, if the user starts talking the worker interrupts
playback so the user can take over the conversation.
"""

from pathlib import Path

from packages.voice_runtime import SpeechSynthesisResult
from packages.voice_worker_runtime import (
    FakeLocalAudioAdapter,
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerBackendRuntime,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
)
from packages.voice_worker_runtime.models import VoiceWorkerEventType


def _backend_with_fake_tts(tmp_path: Path) -> tuple[VoiceWorkerBackendRuntime, VoiceAssetManager]:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "tts" / "kokoro-af-heart").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="kokoro-af-heart", backend_id="kokoro-onnx", model_kind="tts_voice",
            relative_path="tts/kokoro-af-heart", explicit_user_triggered=True,
        )
    )

    def tts_runner(request, asset):
        return SpeechSynthesisResult.succeeded(
            trace_id=request.trace_id, backend_id=asset.backend_id, voice_id=request.voice_id,
            audio_ref="memory://voice/generated/spk", sample_rate=24_000, duration_ms=2000,
        )

    return VoiceWorkerBackendRuntime(asset_manager=manager, tts_runner=tts_runner), manager


def _controller(tmp_path: Path):
    backend, manager = _backend_with_fake_tts(tmp_path)
    audio = FakeLocalAudioAdapter()
    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(), audio=audio, asset_manager=manager, backend_runtime=backend
    )
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))
    return controller, audio


def test_barge_in_interrupts_playback_on_user_speech(tmp_path: Path):
    controller, audio = _controller(tmp_path)
    audio.active_ticks = 10  # playback stays "active" for up to 10 polls
    # VAD: silence for 2 polls, then the user speaks on the 3rd.
    state = {"n": 0}

    def vad(_frame):
        state["n"] += 1
        return state["n"] >= 3

    controller._vad_decider = vad

    result = controller.handle(
        VoiceWorkerCommand(command="speak", command_id="c-speak", payload={"text": "Here is a long answer.", "barge_in": True})
    )

    events = [e.event_type for e in controller.status().recent_events]
    assert VoiceWorkerEventType.BARGE_IN_DETECTED in events
    assert controller.status().playback_status == "interrupted"
    assert result.error is None


def test_barge_in_prefers_echo_cancelled_capture_when_available(tmp_path: Path):
    controller, audio = _controller(tmp_path)
    audio.active_ticks = 1
    calls = {"aec": 0, "raw": 0}

    original_capture = audio.capture_frames

    def capture_echo_cancelled_frames(**kwargs):
        calls["aec"] += 1
        return original_capture(**kwargs)

    def capture_frames(**kwargs):
        calls["raw"] += 1
        return original_capture(**kwargs)

    audio.capture_echo_cancelled_frames = capture_echo_cancelled_frames  # type: ignore[attr-defined]
    audio.capture_frames = capture_frames  # type: ignore[method-assign]
    controller._vad_decider = lambda _frame: False

    controller.handle(
        VoiceWorkerCommand(command="speak", command_id="c-speak", payload={"text": "Echo-cancelled barge-in.", "barge_in": True})
    )

    assert calls["aec"] == 1
    assert calls["raw"] == 0


def test_no_barge_in_plays_to_completion(tmp_path: Path):
    controller, audio = _controller(tmp_path)
    audio.active_ticks = 3  # finishes after 3 polls
    controller._vad_decider = lambda _frame: False  # user never speaks

    controller.handle(
        VoiceWorkerCommand(command="speak", command_id="c-speak", payload={"text": "Short reply.", "barge_in": True})
    )

    events = [e.event_type for e in controller.status().recent_events]
    assert VoiceWorkerEventType.BARGE_IN_DETECTED not in events
    assert VoiceWorkerEventType.PLAYBACK_FINISHED in events


def test_speak_without_barge_in_uses_blocking_play(tmp_path: Path):
    controller, _audio = _controller(tmp_path)
    controller.handle(
        VoiceWorkerCommand(command="speak", command_id="c-speak", payload={"text": "No barge-in here."})
    )
    events = [e.event_type for e in controller.status().recent_events]
    assert VoiceWorkerEventType.PLAYBACK_FINISHED in events
    assert VoiceWorkerEventType.BARGE_IN_DETECTED not in events
