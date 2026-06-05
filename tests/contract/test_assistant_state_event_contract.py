from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.contracts import AssistantStateEvent, AssistantStatusKind


def _make_event(**overrides) -> dict:
    base = {
        "schema_version": "0.1.1-draft",
        "ts": "2026-05-22T12:00:00+00:00",
        "status": AssistantStatusKind.IDLE,
        "detail": "",
        "audio_level": 0.0,
        "session_ref": None,
        "trace_id": None,
        "raw_audio_persisted": False,
    }
    base.update(overrides)
    return base


def test_assistant_state_event_valid_idle() -> None:
    ev = AssistantStateEvent(**_make_event())
    assert ev.status == AssistantStatusKind.IDLE
    assert ev.audio_level == 0.0
    assert ev.raw_audio_persisted is False


def test_assistant_state_event_all_status_kinds() -> None:
    for kind in AssistantStatusKind:
        ev = AssistantStateEvent(**_make_event(status=kind))
        assert ev.status == kind


def test_assistant_state_event_audio_level_boundaries() -> None:
    ev_low = AssistantStateEvent(**_make_event(audio_level=0.0))
    ev_high = AssistantStateEvent(**_make_event(audio_level=1.0))
    ev_mid = AssistantStateEvent(**_make_event(audio_level=0.5))
    assert ev_low.audio_level == 0.0
    assert ev_high.audio_level == 1.0
    assert ev_mid.audio_level == 0.5


def test_assistant_state_event_audio_level_out_of_range_raises() -> None:
    with pytest.raises(ValidationError):
        AssistantStateEvent(**_make_event(audio_level=1.1))
    with pytest.raises(ValidationError):
        AssistantStateEvent(**_make_event(audio_level=-0.01))


def test_assistant_state_event_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        AssistantStateEvent(**_make_event(unknown_field="bad"))


def test_assistant_state_event_raw_audio_persisted_is_always_false() -> None:
    ev = AssistantStateEvent(**_make_event())
    assert ev.raw_audio_persisted is False


def test_assistant_state_event_raw_audio_persisted_cannot_be_true() -> None:
    with pytest.raises(ValidationError):
        AssistantStateEvent(**_make_event(raw_audio_persisted=True))  # type: ignore[arg-type]


def test_assistant_state_event_with_trace_and_session() -> None:
    ev = AssistantStateEvent(**_make_event(
        status=AssistantStatusKind.THINKING,
        detail="reasoning",
        audio_level=0.0,
        trace_id="trace-123",
        session_ref="session-abc",
    ))
    assert ev.trace_id == "trace-123"
    assert ev.session_ref == "session-abc"
    assert ev.detail == "reasoning"


def test_assistant_state_event_schema_version() -> None:
    ev = AssistantStateEvent(**_make_event())
    assert ev.schema_version == "0.1.1-draft"


def test_assistant_status_kind_values() -> None:
    expected = {
        "idle", "listening", "thinking", "working", "using_tools",
        "mcp", "skills", "searching_web", "talking", "asking", "needs_approval",
    }
    actual = {kind.value for kind in AssistantStatusKind}
    assert actual == expected
