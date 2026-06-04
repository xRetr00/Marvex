"""Streaming event contracts (docs/TODO/06).

Neutral, low-level event types shared by provider adapters (which produce a
stream) and the Core streaming driver (which consumes it). Kept here in
``packages.contracts`` so adapters never import ``packages.core`` and vice
versa. Plain frozen dataclasses - no provider/fastapi imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StreamTextDelta:
    """An incremental chunk of assistant text."""

    text: str


@dataclass(frozen=True)
class StreamCompleted:
    """Terminal event. ``output_text`` is the provider's authoritative full text.

    ``tool_calls`` carries any model-authored function calls captured from the
    completed response, in the same engine shape ``send`` returns, so streaming
    is a drop-in for the non-streaming path in the agentic tool loop.
    """

    response_id: str | None
    finish_reason: str
    output_text: str
    tool_calls: list[dict[str, Any]] | None = field(default=None)
    usage: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


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
