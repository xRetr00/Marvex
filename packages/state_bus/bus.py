from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from packages.contracts.state_event import AssistantStateEvent, AssistantStatusKind

# file size justification: state bus is intentionally self-contained to avoid
# god-object coupling; all concurrency, snapshot, subscriber, and idle-event
# helpers live here as a bounded, single-responsibility module.

_SCHEMA_VERSION = "0.1.1-draft"
_MAX_SUBSCRIBERS = 64
_HEARTBEAT_DETAIL = ""


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def _idle_event(session_ref: str | None = None, trace_id: str | None = None) -> AssistantStateEvent:
    return AssistantStateEvent(
        schema_version=_SCHEMA_VERSION,
        ts=_utc_iso(),
        status=AssistantStatusKind.IDLE,
        detail=_HEARTBEAT_DETAIL,
        audio_level=0.0,
        session_ref=session_ref,
        trace_id=trace_id,
        raw_audio_persisted=False,
    )


Subscriber = Callable[[AssistantStateEvent], None]


class AssistantStateBus:
    """Thread-safe, bounded in-process pub/sub state bus.

    Publishers push AssistantStateEvent instances; subscribers receive them.
    The bus holds the latest snapshot so a new subscriber (or HTTP GET) can
    read current state without waiting for the next publish.

    No raw audio, transcript, or sensitive payload is retained.
    """

    def __init__(self, *, max_subscribers: int = _MAX_SUBSCRIBERS) -> None:
        self._lock = threading.Lock()
        self._snapshot: AssistantStateEvent = _idle_event()
        self._subscribers: deque[Subscriber] = deque()
        self._max_subscribers = max_subscribers

    # ------------------------------------------------------------------
    # Publisher API
    # ------------------------------------------------------------------

    def publish(self, event: AssistantStateEvent) -> None:
        """Publish a new state event to all registered subscribers."""
        with self._lock:
            self._snapshot = event
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception:  # noqa: BLE001  subscriber errors must not crash the bus
                pass

    def publish_status(
        self,
        status: AssistantStatusKind,
        *,
        detail: str = "",
        audio_level: float = 0.0,
        session_ref: str | None = None,
        trace_id: str | None = None,
    ) -> AssistantStateEvent:
        """Convenience helper — construct and publish an event, return it."""
        event = AssistantStateEvent(
            schema_version=_SCHEMA_VERSION,
            ts=_utc_iso(),
            status=status,
            detail=detail,
            audio_level=min(max(audio_level, 0.0), 1.0),
            session_ref=session_ref,
            trace_id=trace_id,
            raw_audio_persisted=False,
        )
        self.publish(event)
        return event

    # ------------------------------------------------------------------
    # Subscriber API
    # ------------------------------------------------------------------

    def subscribe(self, callback: Subscriber) -> None:
        """Register a subscriber callback (bounded by max_subscribers)."""
        with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                return
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Subscriber) -> None:
        """Remove a subscriber callback."""
        with self._lock:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Snapshot API
    # ------------------------------------------------------------------

    @property
    def snapshot(self) -> AssistantStateEvent:
        """Return the latest published event (or an idle event if none)."""
        with self._lock:
            return self._snapshot

    # ------------------------------------------------------------------
    # Introspection (safe, no raw data)
    # ------------------------------------------------------------------

    def safe_projection(self) -> dict[str, Any]:
        with self._lock:
            snap = self._snapshot
            sub_count = len(self._subscribers)
        return {
            "status": snap.status.value,
            "ts": snap.ts,
            "audio_level": snap.audio_level,
            "subscriber_count": sub_count,
            "raw_audio_persisted": False,
        }


# Module-level singleton — services/core/main.py wires publishers into this.
_DEFAULT_BUS: AssistantStateBus | None = None
_BUS_LOCK = threading.Lock()


def get_default_bus() -> AssistantStateBus:
    """Return the process-level singleton AssistantStateBus."""
    global _DEFAULT_BUS  # noqa: PLW0603
    with _BUS_LOCK:
        if _DEFAULT_BUS is None:
            _DEFAULT_BUS = AssistantStateBus()
        return _DEFAULT_BUS


def reset_default_bus() -> None:
    """Replace the singleton with a fresh bus.  Test-only helper."""
    global _DEFAULT_BUS  # noqa: PLW0603
    with _BUS_LOCK:
        _DEFAULT_BUS = AssistantStateBus()
