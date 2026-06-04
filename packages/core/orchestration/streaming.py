"""Streaming provider turn driver (docs/TODO/06) — provider-agnostic core.

The foundation of streaming responses: a pure driver that consumes a provider's
incremental output (text deltas), forwards each delta to a sink (the transport /
UI / TTS), and assembles the final text. It is decoupled from any specific
provider, fastapi, and the Core service so it is unit-testable with a fake
streaming provider - exactly like ``run_tool_loop``.

Event model (what a streaming ``stream_send`` yields):
* ``StreamTextDelta(text=...)``    — an incremental chunk of assistant text.
* ``StreamCompleted(response_id, finish_reason, output_text)`` — terminal event;
  ``output_text`` is the provider's authoritative full text (used to reconcile
  against the accumulated deltas).
* ``StreamError(message)``         — the stream failed; caller falls back to the
  non-streaming path.

Non-streaming providers/clients never touch this module; it is additive and
opt-in, so the existing request/response path is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol

# Event types live in packages.contracts so provider adapters and this driver
# share them without crossing the adapter<->core boundary.
from packages.contracts.streaming_models import (
    StreamCompleted,
    StreamError,
    StreamEvent,
    StreamTextDelta,
)


class StreamingProvider(Protocol):
    def stream_send(self, request: object) -> Iterable[StreamEvent]:
        ...


@dataclass
class StreamedTurn:
    status: str  # "completed" | "error"
    text: str
    response_id: str | None = None
    finish_reason: str = "stop"
    delta_count: int = 0
    error_message: str = ""
    deltas: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


# on_delta(text_chunk) -> None. Called for each text delta as it arrives.
DeltaSink = Callable[[str], None]


def run_streaming_turn(
    events: Iterable[StreamEvent],
    *,
    on_delta: DeltaSink | None = None,
) -> StreamedTurn:
    """Drive a provider stream to completion, forwarding deltas to ``on_delta``.

    Accumulates delta text and reconciles it with the terminal event's
    authoritative ``output_text`` (a provider may send a corrected/full final
    string). Returns a ``StreamedTurn`` the caller turns into the usual
    ``AssistantTurnResult`` so persistence, refs, and the response-id chain are
    unchanged.
    """

    accumulated: list[str] = []
    response_id: str | None = None
    finish_reason = "stop"

    for event in events:
        if isinstance(event, StreamTextDelta):
            if not event.text:
                continue
            accumulated.append(event.text)
            if on_delta is not None:
                try:
                    on_delta(event.text)
                except Exception:
                    # A failing sink (UI/transport) must never abort generation.
                    pass
        elif isinstance(event, StreamCompleted):
            response_id = event.response_id
            finish_reason = event.finish_reason or "stop"
            # Prefer the provider's authoritative full text when it is at least
            # as complete as the concatenated deltas; otherwise keep the deltas.
            joined = "".join(accumulated)
            final_text = event.output_text if len(event.output_text) >= len(joined) else joined
            return StreamedTurn(
                status="completed",
                text=final_text,
                response_id=response_id,
                finish_reason=finish_reason,
                delta_count=len(accumulated),
                deltas=list(accumulated),
                tool_calls=event.tool_calls,
                usage=dict(event.usage),
                raw_metadata=dict(event.raw_metadata),
            )
        elif isinstance(event, StreamError):
            return StreamedTurn(
                status="error",
                text="".join(accumulated),
                response_id=response_id,
                finish_reason="error",
                delta_count=len(accumulated),
                error_message=event.message,
                deltas=list(accumulated),
            )

    # Stream ended without an explicit terminal event: treat the accumulated
    # deltas as the final text (graceful, not an error).
    return StreamedTurn(
        status="completed",
        text="".join(accumulated),
        response_id=response_id,
        finish_reason=finish_reason,
        delta_count=len(accumulated),
        deltas=list(accumulated),
    )


__all__ = [
    "StreamTextDelta",
    "StreamCompleted",
    "StreamError",
    "StreamEvent",
    "StreamingProvider",
    "StreamedTurn",
    "DeltaSink",
    "run_streaming_turn",
]
