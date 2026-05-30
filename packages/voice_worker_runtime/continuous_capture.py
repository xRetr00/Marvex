"""Continuous microphone capture for wake word + command listening.

The root cause of "Hey Marvex never triggers": the shipped wake-word model is a
streaming ``chunk-16-left-64`` zipformer that REQUIRES contiguous audio. The old
capture path reopened the input device every tick (``sd.rec`` -> record N
frames -> close, then wait), feeding the streaming spotter disjoint windows with
multi-second gaps. The model's chunked left-context then spanned discontinuous
points in time, so it never matched.

This module provides a SINGLE persistent input stream that delivers back-to-back
~100 ms frames with no gaps and no per-frame device reopening, decoupled from
the worker command lock. The real implementation wraps ``sounddevice``'s
callback-based ``InputStream``; a fake implementation drives the same interface
deterministically for tests.
"""

from __future__ import annotations

import queue
from collections.abc import Iterable
from typing import Any, Protocol

from packages.voice_runtime import AudioFrame
from packages.voice_worker_runtime.audio import VoiceWorkerAudioFrame


class ContinuousCapture(Protocol):
    def start(self) -> None: ...
    def read(self, *, timeout: float = 1.0) -> AudioFrame | None: ...
    def stop(self) -> None: ...
    def active(self) -> bool: ...


class SoundDeviceContinuousCapture:
    """One persistent ``sd.InputStream`` delivering contiguous frames.

    A sounddevice callback pushes fixed-size int16 blocks onto a bounded queue;
    ``read`` pops them as ``AudioFrame``s. The stream is never reopened between
    frames, so the audio handed to the wake-word spotter is gap-free - which is
    what the streaming zipformer needs to detect.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        channels: int = 1,
        frame_ms: int = 100,
        device: int | str | None = None,
        max_queued_frames: int = 200,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = max(1, channels)
        self._frame_samples = max(1, int(sample_rate * frame_ms / 1000))
        self._frame_ms = frame_ms
        self._device = device
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=max_queued_frames)
        self._stream: Any = None
        self._seq = 0

    def start(self) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd  # type: ignore[import-not-found]

        def _callback(indata, _frames, _time_info, _status) -> None:  # noqa: ANN001
            try:
                self._queue.put_nowait(bytes(indata))
            except queue.Full:
                # Drop oldest if the consumer is behind; never block the audio
                # callback (that would glitch the device).
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(bytes(indata))
                except queue.Empty:
                    pass

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            blocksize=self._frame_samples,
            device=self._device,
            callback=_callback,
        )
        self._stream.start()

    def read(self, *, timeout: float = 1.0) -> AudioFrame | None:
        try:
            pcm = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        self._seq += 1
        return VoiceWorkerAudioFrame(
            frame_id=f"mic-{self._seq}",
            pcm=pcm,
            sample_rate=self._sample_rate,
            channel_count=self._channels,
            duration_ms=self._frame_ms,
        )

    def active(self) -> bool:
        return self._stream is not None

    def stop(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass


class FakeContinuousCapture:
    """Scripted continuous capture for tests (no real audio device)."""

    def __init__(self, frames: Iterable[AudioFrame]) -> None:
        self._frames = list(frames)
        self._index = 0
        self._started = False

    def start(self) -> None:
        self._started = True

    def read(self, *, timeout: float = 1.0) -> AudioFrame | None:
        del timeout
        if self._index >= len(self._frames):
            return None
        frame = self._frames[self._index]
        self._index += 1
        return frame

    def active(self) -> bool:
        return self._started

    def remaining(self) -> int:
        return max(0, len(self._frames) - self._index)

    def stop(self) -> None:
        self._started = False


__all__ = [
    "ContinuousCapture",
    "SoundDeviceContinuousCapture",
    "FakeContinuousCapture",
]
