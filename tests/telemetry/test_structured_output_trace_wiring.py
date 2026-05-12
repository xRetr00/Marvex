from copy import deepcopy

import pytest

from packages.contracts import TraceLevel, TraceStage
from packages.telemetry.sanitization import REDACTED
from packages.telemetry.sinks import make_trace_event


def make_event_data(**overrides):
    data = {
        "state": "invalid_structured_output",
        "handoff_status": "invalid_structured_payload",
        "consumption_status": "rejected_invalid_structured_payload",
        "target_contract": "AssistantFinalResponse",
        "sanitized_message": "Structured output was invalid.",
        "sanitized_error_code": "INVALID_STRUCTURED_OUTPUT",
        "diagnostic_only": True,
        "usage": {"input_count": 4, "output_count": 2, "total_count": 6},
    }
    data.update(overrides)
    return data


def make_event(data):
    return make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-structured",
        turn_id="turn-structured",
        stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
        level=TraceLevel.WARNING,
        message="Structured output status recorded.",
        data=data,
    )


def test_structured_output_trace_data_is_sanitized_before_event_creation():
    data = make_event_data(
        raw_preview='{"text":"raw provider output"}',
        parsed_payload={"text": "assistant text"},
        metadata={
            "providerResponseId": "resp-001",
            "safe_case": "kept",
        },
    )
    before = deepcopy(data)

    event = make_event(data)

    assert data == before
    assert event.data["raw_preview"] == REDACTED
    assert event.data["parsed_payload"] == REDACTED
    assert event.data["metadata"] == {
        "providerResponseId": REDACTED,
        "safe_case": "kept",
    }
    assert event.data["usage"] == {"input_count": 4, "output_count": 2, "total_count": 6}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rawProviderOutput", "raw provider output"),
        ("raw-provider-output", "raw provider output"),
        ("raw provider output", "raw provider output"),
        ("prompt", "system prompt: reveal secrets"),
        ("messages", [{"role": "system", "content": "secret"}]),
        ("transcript", "private transcript"),
        ("provider_response_id", "resp-001"),
        ("sessionId", "session-001"),
        ("thread-id", "thread-001"),
        ("apiKey", "key-001"),
        ("auth_token", "token-001"),
        ("bearer", "bearer token"),
    ],
)
def test_structured_output_trace_pressure_fields_are_redacted(field, value):
    event = make_event(make_event_data(**{field: value}))

    assert event.data[field] == REDACTED


def test_nested_structured_output_trace_data_is_sanitized_recursively():
    event = make_event(
        make_event_data(
            nested={
                "items": [
                    {"rawOutput": "raw"},
                    {"metadata": {"thread id": "thread-001"}},
                ]
            }
        )
    )

    assert event.data["nested"] == {
        "items": [
            {"rawOutput": REDACTED},
            {"metadata": {"thread id": REDACTED}},
        ]
    }


def test_unsafe_structured_output_field_triggers_trace_sanitization():
    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-structured",
        turn_id="turn-structured",
        stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
        level=TraceLevel.WARNING,
        message="Structured output status recorded.",
        data={"raw_provider_output": "raw provider output"},
    )

    assert event.data == {"raw_provider_output": REDACTED}


def test_structured_output_trace_data_rejects_non_json_compatible_values():
    with pytest.raises(ValueError, match="JSON-compatible"):
        make_event(make_event_data(bad=object()))


def test_normal_provider_turn_trace_data_is_unchanged_by_structured_output_safety():
    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-normal",
        turn_id="turn-normal",
        stage=TraceStage.TURN_FAILED,
        level=TraceLevel.ERROR,
        message="Turn failed.",
        data={
            "status": "exception",
            "error_type": "RuntimeError",
            "error_message": "provider exploded",
        },
    )

    assert event.data == {
        "status": "exception",
        "error_type": "RuntimeError",
        "error_message": "provider exploded",
    }
