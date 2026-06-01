"""Reference-recording storage for the local-wake wake backend.

local-wake detects a custom phrase ("Hey Marvex") by comparing live audio
against a small set of user-recorded reference WAVs via speech-embedding + DTW -
no model training. This module owns where those reference WAVs live and how
enrollment writes them, so the worker's record command and the local-wake runner
agree on layout. Pure + stdlib only (wave), independently testable.
"""

from __future__ import annotations

import os
import re
import wave
from pathlib import Path

REFERENCE_SUBDIR = "wake-references"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(phrase: str) -> str:
    slug = _SLUG_RE.sub("-", (phrase or "wake").strip().lower()).strip("-")
    return slug or "wake"


def wake_reference_dir(asset_root: str | os.PathLike[str] | None) -> Path:
    """Directory holding the wake reference WAVs (env override wins)."""

    override = os.environ.get("MARVEX_WAKE_REFERENCE_DIR", "").strip()
    if override:
        return Path(override)
    base = Path(asset_root) if asset_root else Path(".marvex-voice-assets")
    return base / REFERENCE_SUBDIR


def list_wake_references(directory: str | os.PathLike[str], *, phrase: str | None = None) -> list[Path]:
    """Sorted reference WAVs in ``directory`` (optionally for one phrase slug)."""

    path = Path(directory)
    if not path.is_dir():
        return []
    prefix = f"{_slug(phrase)}-" if phrase else ""
    return sorted(
        candidate
        for candidate in path.glob("*.wav")
        if candidate.is_file() and (not prefix or candidate.name.startswith(prefix))
    )


def next_reference_path(directory: str | os.PathLike[str], *, phrase: str) -> Path:
    """Next free ``<slug>-NN.wav`` path for an enrollment recording."""

    path = Path(directory)
    slug = _slug(phrase)
    existing = {candidate.name for candidate in path.glob(f"{slug}-*.wav")} if path.is_dir() else set()
    index = 1
    while f"{slug}-{index:02d}.wav" in existing:
        index += 1
    return path / f"{slug}-{index:02d}.wav"


def write_wake_reference_wav(
    path: str | os.PathLike[str],
    pcm_chunks: list[bytes],
    *,
    sample_rate: int,
    channels: int = 1,
    sample_width: int = 2,
) -> dict[str, object]:
    """Write 16-bit PCM chunks to a mono WAV reference file.

    Returns a small status dict (path, byte count, sample_rate). Creates the
    parent directory if needed.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(chunk for chunk in pcm_chunks if chunk)
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(int(channels))
        handle.setsampwidth(int(sample_width))
        handle.setframerate(int(sample_rate))
        handle.writeframes(data)
    return {"path": str(target), "bytes": len(data), "sample_rate": int(sample_rate)}


__all__ = [
    "REFERENCE_SUBDIR",
    "wake_reference_dir",
    "list_wake_references",
    "next_reference_path",
    "write_wake_reference_wav",
]
