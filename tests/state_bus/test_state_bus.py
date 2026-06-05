from __future__ import annotations

import threading
import time

import pytest

from packages.contracts.state_event import AssistantStateEvent, AssistantStatusKind
from packages.state_bus import AssistantStateBus, reset_default_bus


def _make_bus() -> AssistantStateBus:
    return AssistantStateBus()


def _idle_ev(bus: AssistantStateBus) -> AssistantStateEvent:
    return bus.publish_status(AssistantStatusKind.IDLE)


def test_state_bus_snapshot_starts_idle() -> None:
    bus = _make_bus()
    snap = bus.snapshot
    assert snap.status == AssistantStatusKind.IDLE
    assert snap.raw_audio_persisted is False


def test_state_bus_publish_updates_snapshot() -> None:
    bus = _make_bus()
    bus.publish_status(AssistantStatusKind.THINKING, detail="reasoning")
    assert bus.snapshot.status == AssistantStatusKind.THINKING
    assert bus.snapshot.detail == "reasoning"


def test_state_bus_subscriber_receives_event() -> None:
    bus = _make_bus()
    received: list[AssistantStateEvent] = []
    bus.subscribe(received.append)
    bus.publish_status(AssistantStatusKind.WORKING, detail="test")
    assert len(received) == 1
    assert received[0].status == AssistantStatusKind.WORKING


def test_state_bus_unsubscribe_stops_delivery() -> None:
    bus = _make_bus()
    received: list[AssistantStateEvent] = []
    bus.subscribe(received.append)
    bus.publish_status(AssistantStatusKind.THINKING)
    bus.unsubscribe(received.append)
    bus.publish_status(AssistantStatusKind.IDLE)
    assert len(received) == 1


def test_state_bus_bounded_subscriber_limit() -> None:
    bus = AssistantStateBus(max_subscribers=3)
    callbacks = [lambda ev: None for _ in range(5)]
    for cb in callbacks:
        bus.subscribe(cb)
    # Only 3 subscribers should be registered
    assert len(bus._subscribers) == 3  # type: ignore[attr-defined]


def test_state_bus_subscriber_error_does_not_crash_bus() -> None:
    bus = _make_bus()

    def bad_callback(ev: AssistantStateEvent) -> None:
        raise RuntimeError("subscriber error")

    bus.subscribe(bad_callback)
    # Should not raise
    bus.publish_status(AssistantStatusKind.THINKING)
    assert bus.snapshot.status == AssistantStatusKind.THINKING


def test_state_bus_audio_level_clamped_in_publish_status() -> None:
    bus = _make_bus()
    ev = bus.publish_status(AssistantStatusKind.LISTENING, audio_level=1.5)
    assert ev.audio_level == 1.0
    ev2 = bus.publish_status(AssistantStatusKind.LISTENING, audio_level=-0.5)
    assert ev2.audio_level == 0.0


def test_state_bus_audio_level_present_in_events() -> None:
    bus = _make_bus()
    ev = bus.publish_status(AssistantStatusKind.TALKING, audio_level=0.42)
    assert 0.0 <= ev.audio_level <= 1.0
    assert ev.audio_level == pytest.approx(0.42)


def test_state_bus_raw_audio_never_persisted() -> None:
    bus = _make_bus()
    ev = bus.publish_status(AssistantStatusKind.LISTENING, audio_level=0.8)
    assert ev.raw_audio_persisted is False


def test_state_bus_thread_safe_publish() -> None:
    bus = _make_bus()
    errors: list[Exception] = []

    def publish_many() -> None:
        try:
            for _ in range(50):
                bus.publish_status(AssistantStatusKind.WORKING)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert bus.snapshot.status == AssistantStatusKind.WORKING


def test_state_bus_safe_projection() -> None:
    bus = _make_bus()
    bus.publish_status(AssistantStatusKind.THINKING)
    proj = bus.safe_projection()
    assert proj["status"] == "thinking"
    assert proj["raw_audio_persisted"] is False
    assert isinstance(proj["audio_level"], float)


def test_reset_default_bus_gives_fresh_bus() -> None:
    from packages.state_bus import get_default_bus
    reset_default_bus()
    bus = get_default_bus()
    assert bus.snapshot.status == AssistantStatusKind.IDLE
