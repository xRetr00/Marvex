from __future__ import annotations

from array import array
from collections.abc import Callable, Iterable
from typing import Literal, Protocol

from pydantic import Field

from packages.voice_runtime import AudioFrame
from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping


class VoiceAudioDevice(VoiceRuntimeModel):
    device_id: str
    label: str
    host_api: str = "mock"
    max_input_channels: int = 0
    max_output_channels: int = 0
    default_sample_rate: int = 16_000
    is_input: bool = False
    is_output: bool = False

    def safe_projection(self) -> dict[str, object]:
        return safe_mapping(self.model_dump(mode="json"))


class VoiceWorkerAudioFrame(AudioFrame):
    raw_audio_persisted: Literal[False] = False


class MicLevelResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    device_id: str
    status: Literal["passed", "failed", "blocked"]
    peak_level: float = Field(default=0, ge=0, le=1)
    rms_level: float = Field(default=0, ge=0, le=1)
    duration_ms: int = Field(default=0, ge=0)
    raw_audio_persisted: Literal[False] = False


class PlaybackAdapterResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    device_id: str | None = None
    status: Literal["queued", "playing", "completed", "interrupted", "stopped", "failed", "blocked"]
    audio_ref: str | None = None
    reason_code: str = "playback.safe_status"
    raw_audio_persisted: Literal[False] = False


class LocalAudioAdapter(Protocol):
    def list_input_devices(self) -> tuple[VoiceAudioDevice, ...]: ...
    def list_output_devices(self) -> tuple[VoiceAudioDevice, ...]: ...
    def test_mic_level(self, *, device_id: str | None, duration_ms: int) -> MicLevelResult: ...
    def capture_frames(self, *, device_id: str | None, sample_rate: int, channel_count: int, frame_count: int) -> Iterable[AudioFrame]: ...
    def play_audio(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult: ...
    def stop_playback(self) -> PlaybackAdapterResult: ...
    def interrupt_playback(self, *, reason_code: str) -> PlaybackAdapterResult: ...
    # Non-blocking playback for barge-in: begin_playback returns immediately and
    # playback_active reports whether audio is still playing so the worker can
    # monitor the mic and interrupt mid-utterance.
    def begin_playback(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult: ...
    def playback_active(self) -> bool: ...


class FakeLocalAudioAdapter:
    def __init__(self) -> None:
        self._playback_status = "stopped"
        self._last_output: str | None = None
        # Number of playback_active() polls that report "still playing" before
        # completion. Tests set this to simulate playback duration / barge-in.
        self.active_ticks = 0

    def list_input_devices(self) -> tuple[VoiceAudioDevice, ...]:
        return (VoiceAudioDevice(device_id="input-default", label="Default microphone", max_input_channels=1, is_input=True),)

    def list_output_devices(self) -> tuple[VoiceAudioDevice, ...]:
        return (VoiceAudioDevice(device_id="output-default", label="Default speaker", max_output_channels=2, default_sample_rate=24_000, is_output=True),)

    def test_mic_level(self, *, device_id: str | None, duration_ms: int) -> MicLevelResult:
        selected = device_id or self.list_input_devices()[0].device_id
        return MicLevelResult(device_id=selected, status="passed", peak_level=0.42, rms_level=0.18, duration_ms=duration_ms)

    def capture_frames(self, *, device_id: str | None, sample_rate: int, channel_count: int, frame_count: int) -> Iterable[AudioFrame]:
        del device_id
        for index in range(frame_count):
            yield VoiceWorkerAudioFrame(frame_id=f"fake-frame-{index}", pcm=b"\x01\x02" * 160, sample_rate=sample_rate, channel_count=channel_count, duration_ms=100)

    def play_audio(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        del sample_rate
        self._playback_status = "playing"
        self._last_output = device_id or self.list_output_devices()[0].device_id
        return PlaybackAdapterResult(device_id=self._last_output, status="playing", audio_ref=audio_ref)

    def begin_playback(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        del sample_rate
        self._playback_status = "playing"
        self._last_output = device_id or self.list_output_devices()[0].device_id
        return PlaybackAdapterResult(device_id=self._last_output, status="playing", audio_ref=audio_ref)

    def playback_active(self) -> bool:
        if self.active_ticks > 0:
            self.active_ticks -= 1
            return True
        if self._playback_status == "playing":
            self._playback_status = "completed"
        return False

    def complete_playback(self) -> PlaybackAdapterResult:
        self._playback_status = "completed"
        return PlaybackAdapterResult(device_id=self._last_output, status="completed")

    def stop_playback(self) -> PlaybackAdapterResult:
        self._playback_status = "stopped"
        return PlaybackAdapterResult(device_id=self._last_output, status="stopped", reason_code="playback.stopped")

    def interrupt_playback(self, *, reason_code: str) -> PlaybackAdapterResult:
        self._playback_status = "interrupted"
        return PlaybackAdapterResult(device_id=self._last_output, status="interrupted", reason_code=reason_code)


class SoundDeviceAudioAdapter:
    def __init__(self, *, pcm_resolver: Callable[[str], bytes] | None = None) -> None:
        self._sd = None
        self._pcm_resolver = pcm_resolver

    def _sounddevice(self):
        if self._sd is None:
            import sounddevice as sd  # type: ignore[import-not-found]
            self._sd = sd
        return self._sd

    def list_input_devices(self) -> tuple[VoiceAudioDevice, ...]:
        return tuple(device for device in self._devices() if device.is_input)

    def list_output_devices(self) -> tuple[VoiceAudioDevice, ...]:
        return tuple(device for device in self._devices() if device.is_output)

    def _devices(self) -> tuple[VoiceAudioDevice, ...]:
        devices = []
        for index, item in enumerate(self._sounddevice().query_devices()):
            input_channels = int(item.get("max_input_channels", 0))
            output_channels = int(item.get("max_output_channels", 0))
            devices.append(VoiceAudioDevice(device_id=str(index), label=str(item.get("name", f"device-{index}")), host_api="sounddevice", max_input_channels=input_channels, max_output_channels=output_channels, default_sample_rate=int(item.get("default_samplerate", 16_000)), is_input=input_channels > 0, is_output=output_channels > 0))
        return tuple(devices)

    def test_mic_level(self, *, device_id: str | None, duration_ms: int) -> MicLevelResult:
        sd = self._sounddevice()
        sample_rate = 16_000
        samples = max(1, int(sample_rate * duration_ms / 1000))
        recording = sd.rec(samples, samplerate=sample_rate, channels=1, dtype="float32", device=_device_arg(device_id))
        sd.wait()
        peak = _bounded_level(recording.max() if getattr(recording, "size", 0) else 0)
        rms = _bounded_level(recording.mean() if getattr(recording, "size", 0) else 0)
        return MicLevelResult(device_id=device_id or "default", status="passed", duration_ms=duration_ms, peak_level=peak, rms_level=rms)

    def capture_frames(self, *, device_id: str | None, sample_rate: int, channel_count: int, frame_count: int) -> Iterable[AudioFrame]:
        sd = self._sounddevice()
        frame_samples = max(1, int(sample_rate * 0.1))
        total_samples = frame_samples * max(1, frame_count)
        # One contiguous record per tick: opening + closing the input device
        # per 100ms sub-chunk left audible gaps between frames and meant
        # sherpa-onnx KWS never saw a continuous window. A single rec call
        # gives us back-to-back samples with no device-cycling artefacts.
        recording = sd.rec(
            total_samples,
            samplerate=sample_rate,
            channels=channel_count,
            dtype="int16",
            device=_device_arg(device_id),
        )
        sd.wait()
        sample_bytes = 2 * max(1, channel_count)
        chunk_bytes = frame_samples * sample_bytes
        pcm_bytes = recording.tobytes()
        frames: list[VoiceWorkerAudioFrame] = []
        for index in range(frame_count):
            start = index * chunk_bytes
            end = start + chunk_bytes
            slice_bytes = pcm_bytes[start:end] if start < len(pcm_bytes) else b""
            if not slice_bytes:
                break
            frames.append(
                VoiceWorkerAudioFrame(
                    frame_id=f"sounddevice-frame-{index}",
                    pcm=slice_bytes,
                    sample_rate=sample_rate,
                    channel_count=channel_count,
                    duration_ms=100,
                )
            )
        return tuple(frames)

    def play_audio(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        sd = self._sounddevice()
        pcm = self._pcm_resolver(audio_ref) if self._pcm_resolver else b""
        samples = _pcm_to_float_array(pcm) if pcm else [0.0] * max(1, int(sample_rate * 0.05))
        sd.play(samples, samplerate=sample_rate, device=_device_arg(device_id))
        sd.wait()
        return PlaybackAdapterResult(device_id=device_id, audio_ref=audio_ref, status="completed", reason_code="sounddevice.playback_completed")

    def begin_playback(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        # Non-blocking start (no sd.wait) so the worker can monitor the mic for
        # barge-in while audio plays.
        sd = self._sounddevice()
        pcm = self._pcm_resolver(audio_ref) if self._pcm_resolver else b""
        samples = _pcm_to_float_array(pcm) if pcm else [0.0] * max(1, int(sample_rate * 0.05))
        sd.play(samples, samplerate=sample_rate, device=_device_arg(device_id))
        return PlaybackAdapterResult(device_id=device_id, audio_ref=audio_ref, status="playing", reason_code="sounddevice.playback_started")

    def playback_active(self) -> bool:
        try:
            stream = self._sounddevice().get_stream()
            return bool(getattr(stream, "active", False))
        except Exception:
            return False

    def stop_playback(self) -> PlaybackAdapterResult:
        self._sounddevice().stop()
        return PlaybackAdapterResult(status="stopped", reason_code="sounddevice.stop")

    def interrupt_playback(self, *, reason_code: str) -> PlaybackAdapterResult:
        self._sounddevice().stop()
        return PlaybackAdapterResult(status="interrupted", reason_code=reason_code)


def _device_arg(device_id: str | None) -> int | str | None:
    if device_id is None:
        return None
    return int(device_id) if device_id.isdigit() else device_id


def _pcm_to_float_array(pcm: bytes) -> list[float]:
    """Convert raw int16 PCM bytes to a list of float32 samples in [-1, 1]."""
    try:
        import numpy as np

        return (np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0).tolist()
    except Exception:
        pass
    # Pure-Python fallback: strip any trailing odd byte so frombytes doesn't fail.
    safe = pcm[: len(pcm) - (len(pcm) % 2)]
    if not safe:
        return [0.0]
    buf = array("h")
    buf.frombytes(safe)
    return [max(-1.0, min(1.0, s / 32768.0)) for s in buf]


def _bounded_level(value: object) -> float:
    try:
        number = abs(float(value))
    except Exception:
        return 0.0
    if number > 1.0:
        number = number / 32768.0
    return max(0.0, min(1.0, number))
