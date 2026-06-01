"""local-wake wake-word backend (DTW over speech embeddings).

Compares live audio against user-recorded reference WAVs ("Hey Marvex") using
local-wake's embedding+DTW ``compare``. No model training, no Picovoice console -
just a few reference recordings produced by the in-app enrollment flow. This is
the replacement for the brittle sherpa KWS keyword path.

The matcher (``compare_fn``) is injectable so the detection logic is unit-testable
without the ``lwake`` package or a microphone; the default uses
``lwake.compare(window_wav, reference_wav, method="embedding")`` -> distance
(lower = more similar). Detection fires when the best distance across references
is <= the configured threshold.
"""

from __future__ import annotations

import os
import tempfile
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from packages.voice_runtime import AudioFrame, WakeWordDetectionResult

from .assets import VoiceAssetManager, VoiceModelInstallResult
from .wake_enrollment import list_wake_references, write_wake_reference_wav

CompareFn = Callable[[str, str], float]


def _default_compare_fn() -> CompareFn | None:
    try:
        import lwake  # type: ignore
    except Exception:
        return None

    def compare(window_wav: str, reference_wav: str) -> float:
        return float(lwake.compare(window_wav, reference_wav, method="embedding"))

    return compare


class LocalWakeRunner:
    """Wake detection by matching a rolling audio window against references.

    Same call shape as ``SherpaOnnxKwsRunner`` so it drops into
    ``VoiceWorkerBackendRuntime`` behind backend_id ``local-wake``.
    """

    def __init__(
        self,
        *,
        asset_manager: VoiceAssetManager,
        reference_dir: str | os.PathLike[str],
        compare_fn: CompareFn | None = None,
        window_seconds: float = 1.6,
        sample_rate: int = 16_000,
        cooldown_decodes: int = 6,
    ) -> None:
        self.asset_manager = asset_manager
        self.reference_dir = Path(reference_dir)
        self._compare_fn = compare_fn  # None -> resolve lwake lazily
        self._compare_resolved = compare_fn is not None
        self.window_seconds = max(0.4, float(window_seconds))
        self.sample_rate = int(sample_rate)
        self._max_pcm_bytes = int(self.window_seconds * self.sample_rate) * 2  # int16 mono
        self._buffer: deque[bytes] = deque()
        self._buffered_bytes = 0
        self._cooldown_decodes = max(0, int(cooldown_decodes))
        self._cooldown_left = 0

    def _resolve_compare(self) -> CompareFn | None:
        if not self._compare_resolved:
            self._compare_fn = _default_compare_fn()
            self._compare_resolved = True
        return self._compare_fn

    def _references(self) -> list[Path]:
        return list_wake_references(self.reference_dir)

    def _append(self, frames: tuple[AudioFrame, ...]) -> None:
        for frame in frames:
            pcm = getattr(frame, "pcm", b"") or b""
            if not pcm:
                continue
            self._buffer.append(pcm)
            self._buffered_bytes += len(pcm)
        while self._buffered_bytes > self._max_pcm_bytes and len(self._buffer) > 1:
            dropped = self._buffer.popleft()
            self._buffered_bytes -= len(dropped)

    def _not_detected(self, *, asset_backend_id: str, phrase: str, reason: str, confidence: float = 0.0) -> WakeWordDetectionResult:
        return WakeWordDetectionResult(
            detected=False,
            phrase=phrase,
            confidence=confidence,
            backend_id=asset_backend_id,
            reason_code=reason,
        )

    def __call__(
        self,
        frames: tuple[AudioFrame, ...],
        asset: VoiceModelInstallResult,
        *,
        phrase: str,
        threshold: float,
    ) -> WakeWordDetectionResult:
        references = self._references()
        if not references:
            return self._not_detected(asset_backend_id=asset.backend_id, phrase=phrase, reason="local_wake_no_references")
        compare = self._resolve_compare()
        if compare is None:
            return self._not_detected(asset_backend_id=asset.backend_id, phrase=phrase, reason="local_wake_unavailable")

        self._append(frames)
        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            return self._not_detected(asset_backend_id=asset.backend_id, phrase=phrase, reason="local_wake_cooldown")
        # Need at least ~half the window before a meaningful comparison.
        if self._buffered_bytes < self._max_pcm_bytes // 2:
            return self._not_detected(asset_backend_id=asset.backend_id, phrase=phrase, reason="local_wake_buffering")

        try:
            best_distance = self._best_distance(compare, references)
        except Exception as exc:  # never crash the wake loop
            return self._not_detected(
                asset_backend_id=asset.backend_id,
                phrase=phrase,
                reason=f"local_wake_runtime_error:{type(exc).__name__}",
            )
        if best_distance is None:
            return self._not_detected(asset_backend_id=asset.backend_id, phrase=phrase, reason="local_wake_no_match")

        # local-wake distance: lower = more similar. Detect when best <= threshold.
        confidence = max(0.0, min(1.0, 1.0 - best_distance))
        if best_distance <= threshold:
            self._buffer.clear()
            self._buffered_bytes = 0
            self._cooldown_left = self._cooldown_decodes
            return WakeWordDetectionResult.detected(phrase=phrase, confidence=confidence, backend_id=asset.backend_id)
        return self._not_detected(
            asset_backend_id=asset.backend_id,
            phrase=phrase,
            reason="local_wake_below_threshold",
            confidence=confidence,
        )

    def batch_probe(
        self,
        frames: tuple[AudioFrame, ...],
        asset: VoiceModelInstallResult,
        *,
        phrase: str,
        threshold: float,
    ) -> tuple[bool, str]:
        result = self.__call__(frames, asset, phrase=phrase, threshold=threshold)
        return bool(result.detected), (phrase if result.detected else (result.reason_code or ""))

    def _best_distance(self, compare: CompareFn, references: list[Path]) -> float | None:
        with tempfile.TemporaryDirectory(prefix="marvex-wake-") as tmp:
            window_path = Path(tmp) / "window.wav"
            write_wake_reference_wav(
                window_path,
                list(self._buffer),
                sample_rate=self.sample_rate,
            )
            distances: list[float] = []
            for reference in references:
                try:
                    distances.append(float(compare(str(window_path), str(reference))))
                except Exception:
                    continue
            return min(distances) if distances else None


__all__ = ["LocalWakeRunner", "CompareFn"]
