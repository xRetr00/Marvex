"""Streaming event contracts (docs/TODO/06).

Neutral, low-level event types shared by provider adapters (which produce a
stream) and the Core streaming driver (which consumes it). Kept here in
``packages.contracts`` so adapters never import ``packages.core`` and vice
versa. Plain frozen dataclasses - no provider/fastapi imports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamTextDelta:
    """An incremental chunk of assistant text."""

    text: str


@dataclass(frozen=True)
class StreamCompleted:
    """Terminal event. ``output_text`` is the provider's authoritative full text."""

    response_id: str | None
    finish_reason: str
    output_text: str


@dataclass(frozen=True)
class StreamError:
    """The stream failed; the caller falls back to the non-streaming path."""

    message: str


StreamEvent = StreamTextDelta | StreamCompleted | StreamError


__all__ = [
    "StreamTextDelta",
    "StreamCompleted",
    "StreamError",
    "StreamEvent",
]
