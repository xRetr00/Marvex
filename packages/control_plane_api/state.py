from __future__ import annotations

import json
import queue
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from packages.contracts.state_event import AssistantStateEvent, AssistantStatusKind


_SCHEMA_VERSION = "0.1.1-draft"
SSE_HEARTBEAT_INTERVAL_SECONDS = 5.0
SSE_ACTIVE_INTERVAL_SECONDS = 0.04  # ~25 Hz while listening/talking
ACTIVE_STATUSES = frozenset({
    AssistantStatusKind.LISTENING,
    AssistantStatusKind.TALKING,
})

StartResponse = Any


def state_sse_frame(event: AssistantStateEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    return f"data: {payload}\n\n"


def _sse_line(event: AssistantStateEvent) -> bytes:
    return state_sse_frame(event).encode("utf-8")


def state_snapshot_event(*, state_bus: Any | None) -> AssistantStateEvent:
    if state_bus is not None and hasattr(state_bus, "snapshot"):
        return state_bus.snapshot
    return _idle_event()


def handle_state_snapshot(
    *,
    state_bus: Any | None,
) -> tuple[str, dict[str, Any]]:
    """Return the current AssistantStateEvent snapshot as a JSON-serialisable dict."""
    return "200 OK", state_snapshot_event(state_bus=state_bus).model_dump(mode="json")


def handle_state_stream(
    environ: dict[str, Any],
    start_response: StartResponse,
    *,
    state_bus: Any | None,
) -> Iterable[bytes]:
    """Server-Sent Events stream of AssistantStateEvent.

    Uses a plain WSGI generator — no websocket dependency.
    The stream emits:
      - the current snapshot immediately on connect
      - every new publish from the state bus
      - a periodic heartbeat/audio-level frame:
          ~25 Hz while status is listening or talking,
          every 5 s otherwise (idle heartbeat)

    No raw audio or transcript is ever included in any frame.
    """
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/event-stream"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ],
        None,
    )

    # Resolve bus capabilities once — state_bus is Any|None (boundary constraint)
    has_snapshot = state_bus is not None and hasattr(state_bus, "snapshot")
    has_subscribe = state_bus is not None and hasattr(state_bus, "subscribe")
    has_unsubscribe = state_bus is not None and hasattr(state_bus, "unsubscribe")

    event_q: queue.Queue[AssistantStateEvent] = queue.Queue(maxsize=128)

    def _on_event(ev: AssistantStateEvent) -> None:
        try:
            event_q.put_nowait(ev)
        except queue.Full:
            pass  # drop on full — bounded

    if has_subscribe:
        state_bus.subscribe(_on_event)

    try:
        yield _sse_line(state_bus.snapshot if has_snapshot else _idle_event())

        while True:
            snap = state_bus.snapshot if has_snapshot else None
            timeout = SSE_ACTIVE_INTERVAL_SECONDS if (snap is not None and snap.status in ACTIVE_STATUSES) else SSE_HEARTBEAT_INTERVAL_SECONDS
            try:
                ev = event_q.get(timeout=timeout)
                yield _sse_line(ev)
            except queue.Empty:
                yield _sse_line(snap if snap is not None else _idle_event())
    finally:
        if has_unsubscribe:
            state_bus.unsubscribe(_on_event)


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def _idle_event() -> AssistantStateEvent:
    return AssistantStateEvent(
        schema_version=_SCHEMA_VERSION,
        ts=_utc_iso(),
        status=AssistantStatusKind.IDLE,
        detail="",
        audio_level=0.0,
        session_ref=None,
        trace_id=None,
        raw_audio_persisted=False,
    )
