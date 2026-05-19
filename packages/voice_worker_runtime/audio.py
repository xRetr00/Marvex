from __future__ import annotations

from collections.abc import Iterable
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


class FakeLocalAudioAdapter:
    def __init__(self) -> None:
        self._playback_status = "stopped"
        self._last_output: str | None = None

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
    def __init__(self) -> None:
        self._sd = None

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
        return MicLevelResult(device_id=device_id or "default", status="blocked", duration_ms=duration_ms, peak_level=0, rms_level=0)

    def capture_frames(self, *, device_id: str | None, sample_rate: int, channel_count: int, frame_count: int) -> Iterable[AudioFrame]:
        del device_id, sample_rate, channel_count, frame_count
        return ()

    def play_audio(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        del sample_rate
        return PlaybackAdapterResult(device_id=device_id, audio_ref=audio_ref, status="blocked", reason_code="sounddevice_playback_requires_pcm_buffer")  # type: ignore[arg-type]

    def stop_playback(self) -> PlaybackAdapterResult:
        return PlaybackAdapterResult(status="stopped", reason_code="sounddevice.stop")

    def interrupt_playback(self, *, reason_code: str) -> PlaybackAdapterResult:
        self._sounddevice().stop()
        return PlaybackAdapterResult(status="interrupted", reason_code=reason_code)
