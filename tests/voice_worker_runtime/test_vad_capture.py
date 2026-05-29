"""Tests for VAD-endpointed post-wake capture (docs/TODO/04).

Moonshine-v2 (unlike Whisper) does not pad to a fixed window or do internal
long-form chunking - it expects a trimmed utterance. These tests pin the
incremental VAD endpointing that produces that trimmed segment: start on
speech, stop on trailing silence, cap at max utterance, bail on no speech.
"""

from packages.voice_runtime import AudioFrame
from packages.voice_worker_runtime import (
    FakeLocalAudioAdapter,
    VoiceWorkerConfig,
    VoiceWorkerController,
)


class _ScriptedAudio:
    """Yields one frame per capture_frames call from a tagged script.

    Frame ids starting with 's' are speech; 'q' are silence. The injected VAD
    decider reads that tag, so the test controls endpointing deterministically.
    """

    def __init__(self, script: str, sample_rate: int = 16_000):
        self._frames = [
            AudioFrame(frame_id=f"{tag}{i}", pcm=b"\x01\x00" * 160, sample_rate=sample_rate, channel_count=1, duration_ms=100)
            for i, tag in enumerate(script)
        ]
        self._idx = 0

    def capture_frames(self, *, device_id, sample_rate, channel_count, frame_count):
        out = []
        for _ in range(frame_count):
            if self._idx >= len(self._frames):
                break
            out.append(self._frames[self._idx])
            self._idx += 1
        return tuple(out)

    # Unused adapter surface for the controller.
    def list_input_devices(self):
        return ()

    def list_output_devices(self):
        return ()

    def stop_playback(self):
        return None


def _config() -> VoiceWorkerConfig:
    cfg = VoiceWorkerConfig.default()
    return cfg.model_copy(
        update={
            "vad": cfg.vad.model_copy(
                update={"silence_timeout_ms": 300, "tail_padding_ms": 100, "max_utterance_ms": 2000}
            )
        }
    )


def _controller(script: str) -> VoiceWorkerController:
    controller = VoiceWorkerController(config=_config(), audio=_ScriptedAudio(script))
    controller._vad_decider = lambda frame: frame.frame_id.startswith("s")
    return controller


def test_capture_stops_on_trailing_silence():
    # 1 leading silence, 3 speech, then 3 silence -> endpoint after 3 silence.
    controller = _controller("qsssqqq")
    frames, reason = controller._capture_utterance(vad_decider=controller._vad_decider)
    assert reason == "silence_endpoint"
    ids = [f.frame_id for f in frames]
    # pre-roll (1 silence) + 3 speech + 3 trailing-silence frames captured.
    assert any(i.startswith("s") for i in ids)
    assert ids[0].startswith("q")  # pre-roll silence retained before speech


def test_capture_bails_on_no_speech():
    controller = _controller("q" * 40)
    frames, reason = controller._capture_utterance(vad_decider=controller._vad_decider)
    assert reason == "no_speech"


def test_capture_caps_at_max_utterance():
    # Continuous speech, never any trailing silence -> hits max_utterance.
    controller = _controller("s" * 40)
    frames, reason = controller._capture_utterance(vad_decider=controller._vad_decider)
    assert reason == "max_utterance"
    # max_utterance_ms=2000 / 100ms = 20 frames cap.
    assert len(frames) <= 20


def test_resolve_vad_decider_defaults_without_crashing():
    controller = VoiceWorkerController(config=_config(), audio=FakeLocalAudioAdapter())
    decider = controller._resolve_vad_decider()
    frame = AudioFrame(frame_id="f", pcm=b"\x00\x00" * 160, sample_rate=16_000, channel_count=1, duration_ms=100)
    # Default silero adapter is unavailable in the test env; decider must not
    # raise and should return a bool.
    assert isinstance(decider(frame), bool)
