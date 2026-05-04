from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.contracts import (
    AssistantInputSource,
    AssistantMode,
    InputModality,
    Sensitivity,
)
from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)


def test_text_input_creates_valid_input_event():
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        text="Hello",
        source=AssistantInputSource.CLI,
        timestamp=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        session_id="session-001",
    )

    assert event.schema_version == "0.1.1-draft"
    assert event.trace_id == "trace-001"
    assert event.event_id == "event-001"
    assert event.source == AssistantInputSource.CLI
    assert event.input_modality == InputModality.TEXT
    assert event.payload is not None
    assert event.payload.text == "Hello"
    assert event.payload_ref is None
    assert event.session_ref is not None
    assert event.session_ref.ref_id == "session-001"
    assert event.privacy.sensitivity == Sensitivity.NORMAL
    assert event.metadata == {}


def test_text_input_creates_valid_assistant_turn_input():
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        text="Hello",
        timestamp=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        session_id="session-001",
    )

    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_event=event,
        identity_id="identity-001",
        assistant_mode=AssistantMode.DEFAULT,
    )

    assert turn_input.schema_version == "0.1.1-draft"
    assert turn_input.trace_id == "trace-001"
    assert turn_input.turn_id == "turn-001"
    assert turn_input.input_event_id == "event-001"
    assert turn_input.session_ref is not None
    assert turn_input.session_ref.ref_id == "session-001"
    assert turn_input.identity_ref is not None
    assert turn_input.identity_ref.ref_id == "identity-001"
    assert turn_input.user_visible_input == "Hello"
    assert turn_input.policy_context.requested_capabilities == []
    assert turn_input.metadata == {}


def test_turn_input_rejects_mismatched_trace_id():
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        text="Hello",
        timestamp=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="trace_id"):
        build_turn_input_from_event(
            schema_version="0.1.1-draft",
            trace_id="trace-002",
            turn_id="turn-001",
            input_event=event,
        )


def test_assistant_runtime_does_not_import_forbidden_packages():
    runtime_dir = Path("packages/assistant_runtime")
    forbidden_imports = (
        "packages.core",
        "packages.provider_runtime",
        "packages.adapters",
        "packages.ports",
        "apps.cli",
        "services.",
    )

    for path in runtime_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in text
