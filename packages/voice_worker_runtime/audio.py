from __future__ import annotations

from array import array
from collections.abc import Callable, Iterable
from math import floor, sqrt
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
    is_default_input: bool = False
    is_default_output: bool = False

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
        return (VoiceAudioDevice(device_id="input-default", label="Default microphone", max_input_channels=1, is_input=True, is_default_input=True),)

    def list_output_devices(self) -> tuple[VoiceAudioDevice, ...]:
        return (VoiceAudioDevice(device_id="output-default", label="Default speaker", max_output_channels=2, default_sample_rate=24_000, is_output=True, is_default_output=True),)

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
        self._last_playback_pcm = b""
        self._last_playback_sample_rate = 0
        self._aec: _WebRtcAecProcessor | None = None

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
        default_input_id, default_output_id = _default_device_ids(self._sounddevice())
        for index, item in enumerate(self._sounddevice().query_devices()):
            input_channels = int(item.get("max_input_channels", 0))
            output_channels = int(item.get("max_output_channels", 0))
            device_id = str(index)
            devices.append(VoiceAudioDevice(device_id=device_id, label=str(item.get("name", f"device-{index}")), host_api="sounddevice", max_input_channels=input_channels, max_output_channels=output_channels, default_sample_rate=int(item.get("default_samplerate", 16_000)), is_input=input_channels > 0, is_output=output_channels > 0, is_default_input=device_id == default_input_id, is_default_output=device_id == default_output_id))
        return tuple(devices)

    def test_mic_level(self, *, device_id: str | None, duration_ms: int) -> MicLevelResult:
        sd = self._sounddevice()
        sample_rate = 16_000
        samples = max(1, int(sample_rate * duration_ms / 1000))
        selected_device_id = device_id or _default_device_ids(sd)[0]
        recording = sd.rec(samples, samplerate=sample_rate, channels=1, dtype="float32", device=_device_arg(selected_device_id))
        sd.wait()
        peak, rms = _recording_peak_and_rms(recording)
        return MicLevelResult(device_id=selected_device_id or "default", status="passed", duration_ms=duration_ms, peak_level=peak, rms_level=rms)

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

    def capture_echo_cancelled_frames(self, *, device_id: str | None, sample_rate: int, channel_count: int, frame_count: int) -> Iterable[AudioFrame]:
        frames = tuple(self.capture_frames(device_id=device_id, sample_rate=sample_rate, channel_count=channel_count, frame_count=frame_count))
        if not frames:
            return ()
        aec = self._ensure_aec(sample_rate=sample_rate, channel_count=channel_count)
        if aec is None:
            return frames
        return tuple(aec.process_frame(frame) for frame in frames)

    def play_audio(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        sd = self._sounddevice()
        pcm = self._pcm_resolver(audio_ref) if self._pcm_resolver else b""
        self._remember_far_end(pcm=pcm, sample_rate=sample_rate)
        samples = _pcm_to_float_array(pcm) if pcm else [0.0] * max(1, int(sample_rate * 0.05))
        sd.play(samples, samplerate=sample_rate, device=_device_arg(device_id))
        sd.wait()
        return PlaybackAdapterResult(device_id=device_id, audio_ref=audio_ref, status="completed", reason_code="sounddevice.playback_completed")

    def begin_playback(self, *, device_id: str | None, audio_ref: str, sample_rate: int) -> PlaybackAdapterResult:
        # Non-blocking start (no sd.wait) so the worker can monitor the mic for
        # barge-in while audio plays.
        sd = self._sounddevice()
        pcm = self._pcm_resolver(audio_ref) if self._pcm_resolver else b""
        self._remember_far_end(pcm=pcm, sample_rate=sample_rate)
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

    def _remember_far_end(self, *, pcm: bytes, sample_rate: int) -> None:
        self._last_playback_pcm = pcm or b""
        self._last_playback_sample_rate = int(sample_rate or 0)
        self._aec = None

    def _ensure_aec(self, *, sample_rate: int, channel_count: int) -> "_WebRtcAecProcessor | None":
        if not self._last_playback_pcm:
            return None
        if self._aec is None or self._aec.sample_rate != sample_rate or self._aec.channel_count != channel_count:
            try:
                self._aec = _WebRtcAecProcessor(sample_rate=sample_rate, channel_count=channel_count)
                far_end = _resample_pcm_int16(self._last_playback_pcm, source_rate=self._last_playback_sample_rate, target_rate=sample_rate)
                self._aec.set_far_end(far_end)
            except Exception:
                self._aec = None
        return self._aec


class _WebRtcAecProcessor:
    """Small adapter over ``aec-audio-processing`` WebRTC APM.

    The library operates on 10 ms int16 PCM frames and needs the far-end
    playback signal as a reverse stream. We keep that detail inside the local
    audio adapter so barge-in/VAD only sees cleaned mic frames.
    """

    def __init__(self, *, sample_rate: int, channel_count: int) -> None:
        from aec_audio_processing import AudioProcessor  # type: ignore[import-not-found]

        self.sample_rate = int(sample_rate)
        self.channel_count = int(channel_count)
        self.chunk_bytes = max(1, self.sample_rate // 100) * max(1, self.channel_count) * 2
        self._far_end = b""
        self._far_offset = 0
        self._processor = AudioProcessor(enable_aec=True, enable_ns=True, enable_agc=False, enable_vad=False)
        self._processor.set_stream_format(self.sample_rate, self.channel_count, self.sample_rate, self.channel_count)
        self._processor.set_reverse_stream_format(self.sample_rate, self.channel_count)
        self._processor.set_stream_delay(50)

    def set_far_end(self, pcm: bytes) -> None:
        self._far_end = pcm[: len(pcm) - (len(pcm) % 2)]
        self._far_offset = 0

    def process_frame(self, frame: AudioFrame) -> VoiceWorkerAudioFrame:
        cleaned = bytearray()
        pcm = frame.pcm[: len(frame.pcm) - (len(frame.pcm) % 2)]
        for start in range(0, len(pcm), self.chunk_bytes):
            chunk = pcm[start:start + self.chunk_bytes]
            if len(chunk) < self.chunk_bytes:
                cleaned.extend(chunk)
                continue
            reverse = self._next_far_end_chunk(len(chunk))
            try:
                self._processor.process_reverse_stream(reverse)
                out = self._processor.process_stream(chunk)
                cleaned.extend(bytes(out))
            except Exception:
                cleaned.extend(chunk)
        return VoiceWorkerAudioFrame(
            frame_id=frame.frame_id,
            pcm=bytes(cleaned) or frame.pcm,
            sample_rate=frame.sample_rate,
            channel_count=frame.channel_count,
            duration_ms=frame.duration_ms,
        )

    def _next_far_end_chunk(self, size: int) -> bytes:
        if self._far_offset >= len(self._far_end):
            return b"\x00" * size
        chunk = self._far_end[self._far_offset:self._far_offset + size]
        self._far_offset += size
        if len(chunk) < size:
            chunk += b"\x00" * (size - len(chunk))
        return chunk


def _device_arg(device_id: str | None) -> int | str | None:
    if device_id is None:
        return None
    return int(device_id) if device_id.isdigit() else device_id


def _default_device_ids(sd: object) -> tuple[str | None, str | None]:
    try:
        default = getattr(sd, "default", None)
        device = getattr(default, "device", None)
    except Exception:
        return None, None
    if isinstance(device, (list, tuple)) or hasattr(device, "__getitem__"):
        input_id = _device_id_from_pair(device, 0)
        output_id = _device_id_from_pair(device, 1)
        return input_id, output_id
    resolved = _device_id_from_default(device)
    return resolved, None


def _device_id_from_pair(value: object, index: int) -> str | None:
    try:
        return _device_id_from_default(value[index])  # type: ignore[index]
    except Exception:
        return None


def _device_id_from_default(value: object) -> str | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except Exception:
        return None
    return str(number) if number >= 0 else None


def _recording_peak_and_rms(recording: object) -> tuple[float, float]:
    try:
        import numpy as np

        values = np.asarray(recording, dtype=np.float32)
        if values.size == 0:
            return 0.0, 0.0
        peak = _bounded_level(float(np.max(np.abs(values))))
        rms = _bounded_level(float(np.sqrt(np.mean(np.square(values)))))
        return peak, rms
    except Exception:
        pass
    try:
        raw_values = list(recording)  # type: ignore[arg-type]
    except Exception:
        raw_values = []
    flat: list[float] = []
    for value in raw_values:
        if isinstance(value, (list, tuple)):
            for item in value:
                try:
                    flat.append(float(item))
                except Exception:
                    pass
            continue
        try:
            flat.append(float(value))
        except Exception:
            pass
    if not flat:
        legacy_peak = getattr(recording, "max", None)
        legacy_mean = getattr(recording, "mean", None)
        if callable(legacy_peak) or callable(legacy_mean):
            peak_value = legacy_peak() if callable(legacy_peak) else 0
            mean_value = legacy_mean() if callable(legacy_mean) else 0
            return _bounded_level(peak_value), _bounded_level(mean_value)
        return 0.0, 0.0
    peak = _bounded_level(max(abs(value) for value in flat))
    rms = _bounded_level(sqrt(sum(value * value for value in flat) / len(flat)))
    return peak, rms


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


def _resample_pcm_int16(pcm: bytes, *, source_rate: int, target_rate: int) -> bytes:
    if not pcm or source_rate <= 0 or target_rate <= 0 or source_rate == target_rate:
        return pcm
    safe = pcm[: len(pcm) - (len(pcm) % 2)]
    if not safe:
        return b""
    try:
        import numpy as np

        samples = np.frombuffer(safe, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return b""
        target_count = max(1, int(round(samples.size * target_rate / source_rate)))
        old_x = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        new_x = np.linspace(0.0, 1.0, num=target_count, endpoint=False)
        return np.interp(new_x, old_x, samples).astype(np.int16).tobytes()
    except Exception:
        pass
    src = array("h")
    src.frombytes(safe)
    if not src:
        return b""
    target_count = max(1, int(round(len(src) * target_rate / source_rate)))
    out = array("h")
    for index in range(target_count):
        src_index = min(len(src) - 1, int(floor(index * source_rate / target_rate)))
        out.append(src[src_index])
    return out.tobytes()


def _bounded_level(value: object) -> float:
    try:
        number = abs(float(value))
    except Exception:
        return 0.0
    if number > 1.0:
        number = number / 32768.0
    return max(0.0, min(1.0, number))
