"""Tests for the on-demand `listen` command (continuous multi-turn voice)."""

from pathlib import Path

from packages.voice_runtime import AudioFrame, TranscriptionResult
from packages.voice_worker_runtime import (
    VoiceAssetManager,
    VoiceModelInstallRequest,
    VoiceWorkerBackendRuntime,
    VoiceWorkerCommand,
    VoiceWorkerConfig,
    VoiceWorkerController,
)
from packages.voice_worker_runtime.models import VoiceWorkerEventType


class _ScriptedAudio:
    def __init__(self, script: str):
        self._frames = [
            AudioFrame(frame_id=f"{tag}{i}", pcm=b"\x01\x00" * 160, sample_rate=16_000, channel_count=1, duration_ms=100)
            for i, tag in enumerate(script)
        ]
        self._idx = 0

    def capture_frames(self, *, device_id, sample_rate, channel_count, frame_count):
        out = []
        for _ in range(frame_count):
            if self._idx >= len(self._frames):
                break
            out.append(self._frames[self._idx]); self._idx += 1
        return tuple(out)

    def list_input_devices(self):
        return ()

    def list_output_devices(self):
        return ()

    def stop_playback(self):
        return None


def _stt_manager(tmp_path: Path) -> tuple[VoiceWorkerBackendRuntime, VoiceAssetManager, list]:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    (tmp_path / "voice-assets" / "stt" / "moonshine-v2").mkdir(parents=True)
    manager.install_local(
        VoiceModelInstallRequest(
            model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt",
            relative_path="stt/moonshine-v2", explicit_user_triggered=True,
        )
    )
    calls: list[str] = []

    def stt_runner(request, asset):
        calls.append(request.audio_ref_id)
        return TranscriptionResult.succeeded(
            trace_id=request.trace_id, text="open the report", backend_id=asset.backend_id,
            duration_ms=request.duration_ms, language="en", segments=(),
        )

    return VoiceWorkerBackendRuntime(asset_manager=manager, stt_runner=stt_runner), manager, calls


def test_listen_captures_follow_up_and_emits_transcript(tmp_path: Path):
    backend, manager, _calls = _stt_manager(tmp_path)
    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(), audio=_ScriptedAudio("qsssqqq"), asset_manager=manager, backend_runtime=backend
    )
    controller._vad_decider = lambda frame: frame.frame_id.startswith("s")
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))

    result = controller.handle(VoiceWorkerCommand(command="listen", command_id="c-listen"))

    events = controller.status().recent_events
    completed = next((e for e in reversed(events) if e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED), None)
    assert completed is not None
    assert completed.summary.get("transcript_text") == "open the report"
    assert result.error is None


def test_listen_silence_emits_no_transcript(tmp_path: Path):
    backend, manager, _calls = _stt_manager(tmp_path)
    controller = VoiceWorkerController(
        config=VoiceWorkerConfig.default(), audio=_ScriptedAudio("q" * 40), asset_manager=manager, backend_runtime=backend
    )
    controller._vad_decider = lambda frame: False  # pure silence
    controller.handle(VoiceWorkerCommand(command="start", command_id="c-start"))

    controller.handle(VoiceWorkerCommand(command="listen", command_id="c-listen"))

    events = controller.status().recent_events
    assert not any(
        e.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED and e.summary.get("transcript_text")
        for e in events
    )
