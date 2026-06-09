"""Tests for the voice worker `speak` command (docs/TODO/04).

`speak` closes the voice loop: the shell submits the recognized transcript as
a chat turn, then sends the reply text here to be synthesized and played.
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


def _backend_with_fake_tts(tmp_path: Path) -> tuple[VoiceWorkerBackendRuntime, VoiceAssetManager, list]:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "tts" / "supertonic-v2").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="supertonic-v2",
            backend_id="supertonic-v2",
            model_kind="tts_voice",
            relative_path="tts/supertonic-v2",
            explicit_user_triggered=True,
        )
    )
    spoken: list[str] = []

    def tts_runner(request, asset):
        spoken.append(request.text)
        return SpeechSynthesisResult.succeeded(
            trace_id=request.trace_id,
            backend_id=asset.backend_id,
            voice_id=request.voice_id,
            audio_ref="memory://voice/generated/spk",
            sample_rate=24_000,
            duration_ms=400,
        )

    backend = VoiceWorkerBackendRuntime(asset_manager=manager, tts_runner=tts_runner)
    return backend, manager, spoken


def test_speak_synthesizes_and_plays_reply(tmp_path: Path):
    backend, manager, spoken = _backend_with_fake_tts(tmp_path)
    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=backend,
    )
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))

    result = controller.handle(
        VoiceWorkerCommand(command="speak", command_id="c-speak", payload={"text": "Open source means publicly available source code."})
    )

    assert spoken == ["Open source means publicly available source code."]
    events = [e.event_type for e in controller.status().recent_events]
    assert VoiceWorkerEventType.TTS_STARTED in events
    assert VoiceWorkerEventType.PLAYBACK_FINISHED in events
    assert result.error is None


def test_speak_empty_text_is_rejected(tmp_path: Path):
    backend, manager, _spoken = _backend_with_fake_tts(tmp_path)
    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(),
        audio=FakeLocalAudioAdapter(),
        asset_manager=manager,
        backend_runtime=backend,
    )
    result = controller.handle(VoiceWorkerCommand(command="speak", command_id="c-empty", payload={"text": "   "}))
    assert result.event.event_type == VoiceWorkerEventType.ERROR
    assert result.event.summary.get("reason_code") == "speak_text_required"
