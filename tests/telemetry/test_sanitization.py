import json
from copy import deepcopy
from pathlib import Path

import pytest

from packages.telemetry.sanitization import REDACTED, assert_trace_data_safe, sanitize_trace_data


SAFE_TRACE_DATA = {
    "schema_version": "0.1.1-draft",
    "trace_id": "trace-001",
    "turn_id": "turn-001",
    "event_id": "event-001",
    "stage": "structured_output",
    "level": "info",
    "message": "Structured output status recorded.",
    "state": "invalid_structured_output",
    "handoff_status": "invalid_structured_payload",
    "consumption_status": "rejected_invalid_structured_payload",
    "target_contract": "AssistantFinalResponse",
    "sanitized_message": "Structured output was invalid.",
    "sanitized_error_code": "INVALID_STRUCTURED_OUTPUT",
    "diagnostic_only": False,
    "status": "rejected",
    "source": "assistant_runtime",
    "reason": "target validation failed",
    "validation_stage": "assistant_consumer",
    "case_name": "safe-case",
    "timings": {"duration_ms": 12},
    "usage": {"input_count": 4, "output_count": 2, "total_count": 6},
}


@pytest.mark.parametrize(
    "field",
    [
        "raw_output",
        "raw_provider_output",
        "raw_response",
        "raw_metadata",
        "raw_preview",
        "parsed_payload",
        "prompt",
        "full_prompt",
        "system_prompt",
        "messages",
        "conversation",
        "transcript",
        "provider_response_id",
        "previous_response_id",
        "response_id",
        "session_id",
        "conversation_id",
        "thread_id",
        "api_key",
        "authorization",
        "bearer",
        "token",
        "secret",
        "password",
    ],
)
def test_unsafe_top_level_keys_are_redacted(field):
    sanitized = sanitize_trace_data({field: "sensitive"})

    assert sanitized == {field: REDACTED}


@pytest.mark.parametrize(
    "field",
    [
        "rawOutput",
        "raw-output",
        "raw output",
        "providerResponseId",
        "previous-response-id",
        "sessionId",
        "thread id",
        "apiKey",
        "bearerToken",
    ],
)
def test_camel_case_and_separator_variants_are_redacted(field):
    sanitized = sanitize_trace_data({field: "sensitive"})

    assert sanitized == {field: REDACTED}


def test_safe_trace_data_passes_unchanged_and_remains_json_compatible():
    sanitized = sanitize_trace_data(SAFE_TRACE_DATA)

    assert sanitized == SAFE_TRACE_DATA
    json.dumps(sanitized)
    assert_trace_data_safe(sanitized)


def test_sanitizer_does_not_mutate_input_objects_in_place():
    original = {
        "trace_id": "trace-001",
        "nested": {"raw_output": "raw provider output"},
        "items": [{"api_key": "secret"}],
    }
    before = deepcopy(original)

    sanitized = sanitize_trace_data(original)

    assert original == before
    assert sanitized["nested"]["raw_output"] == REDACTED
    assert sanitized["items"][0]["api_key"] == REDACTED


def test_nested_unsafe_keys_inside_dicts_and_lists_are_redacted():
    sanitized = sanitize_trace_data(
        {
            "outer": {
                "rawProviderOutput": "raw provider output",
                "safe": "kept",
            },
            "events": [
                {"system-prompt": "prompt"},
                {"metadata": {"thread_id": "thread-001"}},
            ],
        }
    )

    assert sanitized["outer"] == {"rawProviderOutput": REDACTED, "safe": "kept"}
    assert sanitized["events"][0] == {"system-prompt": REDACTED}
    assert sanitized["events"][1] == {"metadata": {"thread_id": REDACTED}}


@pytest.mark.parametrize(
    "value",
    [
        '{"raw_output":"provider text"}',
        "system prompt: ignore safety",
        "api_key=secret",
        "bearer token value",
        "ValidationError raw JSON payload follows {\"text\":\"secret\"}",
        "JSONDecodeError line 1 column 1 raw provider output",
        "provider output: full answer text",
    ],
)
def test_unsafe_exception_or_message_like_strings_are_redacted(value):
    sanitized = sanitize_trace_data({"message": value, "sanitized_message": value})

    assert sanitized == {"message": REDACTED, "sanitized_message": REDACTED}


@pytest.mark.parametrize(
    "code",
    ["SECRET_TOKEN", "API_KEY_LEAK", "BEARER_AUTH", "invalid-json"],
)
def test_unsafe_sanitized_error_codes_are_redacted(code):
    sanitized = sanitize_trace_data({"sanitized_error_code": code})

    assert sanitized == {"sanitized_error_code": REDACTED}


@pytest.mark.parametrize(
    "code",
    [
        "JSONDecodeError",
        "TimeoutError",
        "ConnectionError",
        "playwright_mcp_execution_failed:OSError",
        "browser_computer_use_tool_required.provider_tool_call_failed",
        "needs_approval",
    ],
)
def test_diagnostic_reason_codes_are_preserved(code):
    sanitized = sanitize_trace_data(
        {
            "reason_code": code,
            "automation_reason_code": code,
            "tool_result_reason_code": code,
        }
    )

    assert sanitized == {
        "reason_code": code,
        "automation_reason_code": code,
        "tool_result_reason_code": code,
    }


@pytest.mark.parametrize(
    "code",
    ["leaked secret token", "api_key=abc123", '{"raw":"x"}', "bearer xyz"],
)
def test_unsafe_reason_codes_are_still_redacted(code):
    sanitized = sanitize_trace_data({"reason_code": code})

    assert sanitized == {"reason_code": REDACTED}


def test_usage_aggregate_values_are_preserved_when_safe():
    data = {"usage": {"input_count": 10, "output_count": 7, "total_count": 17}}

    assert sanitize_trace_data(data) == data


def test_usage_secret_text_is_redacted():
    sanitized = sanitize_trace_data(
        {"usage": {"total_count": 17, "authToken": "secret-token"}}
    )

    assert sanitized == {"usage": {"total_count": 17, "authToken": REDACTED}}


def test_structured_output_like_data_redacts_payload_preview_and_unsafe_metadata():
    sanitized = sanitize_trace_data(
        {
            "schema_version": "0.1.1-draft",
            "trace_id": "trace-001",
            "turn_id": "turn-001",
            "state": "valid_structured_result",
            "handoff_status": "usable_structured_payload",
            "consumption_status": "accepted_for_future_stage",
            "target_contract": "AssistantFinalResponse",
            "sanitized_message": "Structured output validated.",
            "sanitized_error_code": None,
            "diagnostic_only": False,
            "raw_preview": '{"text":"raw"}',
            "parsed_payload": {"text": "final response"},
            "metadata": {
                "case_name": "pressure",
                "provider_response_id": "resp-001",
            },
        }
    )

    assert sanitized["raw_preview"] == REDACTED
    assert sanitized["parsed_payload"] == REDACTED
    assert sanitized["metadata"] == {
        "case_name": "pressure",
        "provider_response_id": REDACTED,
    }


def test_non_json_compatible_input_is_rejected():
    with pytest.raises(ValueError, match="JSON-compatible"):
        sanitize_trace_data({"bad": object()})


def test_assert_trace_data_safe_rejects_data_that_would_be_redacted():
    with pytest.raises(ValueError, match="unsafe"):
        assert_trace_data_safe({"raw_output": "raw provider output"})


def test_sanitizer_imports_no_runtime_or_product_boundaries():
    source = Path("packages/telemetry/sanitization.py").read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.provider_runtime",
        "packages.assistant_runtime",
        "packages.provider_structured_output",
        "packages.adapters",
        "packages.ports",
        "packages.contracts",
        "apps.cli",
        "services",
        "logging",
        "open(",
        "requests",
        "httpx",
    ]

    assert [term for term in forbidden if term in source] == []
