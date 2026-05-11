import pytest
from pydantic import ValidationError

from packages.provider_structured_output import (
    StructuredOutputFallbackResult,
    create_incomplete_unresolved,
    create_invalid_structured_output,
    create_provider_error,
    create_provider_timeout,
    create_refusal_unresolved,
    create_valid_structured_result,
)


def test_valid_result_with_parsed_payload():
    result = create_valid_structured_result(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        target_contract="AssistantFinalResponse",
        parsed_payload={"text": "Done."},
    )

    assert isinstance(result, StructuredOutputFallbackResult)
    assert result.state == "valid_structured_result"
    assert result.parsed_payload == {"text": "Done."}
    assert result.raw_preview is None
    assert result.sanitized_error_code is None
    assert result.metadata == {}


@pytest.mark.parametrize(
    ("error_code", "message"),
    [
        ("INVALID_JSON", "Structured output was not valid JSON."),
        ("VALIDATION_FAILED", "Structured output failed target validation."),
    ],
)
def test_invalid_structured_output_mapping(error_code: str, message: str):
    result = create_invalid_structured_output(
        schema_version="0.1.1-draft",
        trace_id="trace-invalid",
        turn_id="turn-invalid",
        target_contract="AssistantFinalResponse",
        sanitized_error_code=error_code,
        sanitized_message=message,
    )

    assert result.state == "invalid_structured_output"
    assert result.parsed_payload is None
    assert result.sanitized_error_code == error_code
    assert result.sanitized_message == message


def test_provider_error_mapping_sanitizes_exception_message():
    result = create_provider_error(
        schema_version="0.1.1-draft",
        trace_id="trace-error",
        turn_id="turn-error",
        target_contract="AssistantFinalResponse",
        error=RuntimeError("secret raw provider output"),
    )

    assert result.state == "provider_error"
    assert result.sanitized_error_code == "PROVIDER_ERROR"
    assert "secret raw provider output" not in result.sanitized_message
    assert "RuntimeError" not in result.sanitized_message
    assert result.sanitized_message == "Provider error occurred."


def test_provider_timeout_mapping():
    result = create_provider_timeout(
        schema_version="0.1.1-draft",
        trace_id="trace-timeout",
        turn_id="turn-timeout",
        target_contract="AssistantFinalResponse",
    )

    assert result.state == "provider_timeout"
    assert result.sanitized_error_code == "PROVIDER_TIMEOUT"
    assert result.parsed_payload is None


def test_refusal_unresolved_state():
    result = create_refusal_unresolved(
        schema_version="0.1.1-draft",
        trace_id="trace-refusal",
        turn_id="turn-refusal",
        target_contract="AssistantFinalResponse",
    )

    assert result.state == "refusal_unresolved_or_provider_specific"
    assert result.sanitized_error_code == "REFUSAL_UNRESOLVED"


def test_incomplete_unresolved_state():
    result = create_incomplete_unresolved(
        schema_version="0.1.1-draft",
        trace_id="trace-incomplete",
        turn_id="turn-incomplete",
        target_contract="AssistantFinalResponse",
    )

    assert result.state == "incomplete_unresolved_or_provider_specific"
    assert result.sanitized_error_code == "INCOMPLETE_UNRESOLVED"


def test_raw_preview_is_null_by_default_and_bounded_when_present():
    default_result = create_invalid_structured_output(
        schema_version="0.1.1-draft",
        trace_id="trace-preview-default",
        turn_id="turn-preview-default",
        target_contract="AssistantFinalResponse",
    )
    preview_result = create_invalid_structured_output(
        schema_version="0.1.1-draft",
        trace_id="trace-preview",
        turn_id="turn-preview",
        target_contract="AssistantFinalResponse",
        raw_preview="x" * 300,
    )

    assert default_result.raw_preview is None
    assert preview_result.raw_preview == "x" * 300
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-preview-too-long",
            turn_id="turn-preview-too-long",
            target_contract="AssistantFinalResponse",
            raw_preview="x" * 301,
        )


def test_direct_pydantic_validation_exception_is_not_copied():
    try:
        StructuredOutputFallbackResult(
            schema_version="0.1.1-draft",
            trace_id="trace-validation",
            turn_id="turn-validation",
            state="valid_structured_result",
            target_contract="AssistantFinalResponse",
            sanitized_message="",
            sanitized_error_code=None,
            parsed_payload={"text": "Done."},
            raw_preview=None,
            metadata={},
        )
    except ValidationError as exc:
        result = create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-validation",
            turn_id="turn-validation",
            target_contract="AssistantFinalResponse",
            validation_error=exc,
        )
    else:
        raise AssertionError("expected validation error")

    assert result.sanitized_message == "Structured output failed target validation."
    assert "sanitized_message" not in result.sanitized_message


def test_unknown_top_level_fields_rejected():
    with pytest.raises(ValidationError):
        StructuredOutputFallbackResult(
            schema_version="0.1.1-draft",
            trace_id="trace-extra",
            turn_id="turn-extra",
            state="valid_structured_result",
            target_contract="AssistantFinalResponse",
            sanitized_message="Structured output validated.",
            sanitized_error_code=None,
            parsed_payload={"text": "Done."},
            raw_preview=None,
            metadata={},
            raw_provider_output="secret",
        )


def test_sanitized_error_code_shape_and_required_strings():
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-code",
            turn_id="turn-code",
            target_contract="AssistantFinalResponse",
            sanitized_error_code="not stable",
        )
    with pytest.raises(ValidationError):
        create_valid_structured_result(
            schema_version="",
            trace_id="trace-code",
            turn_id="turn-code",
            target_contract="AssistantFinalResponse",
            parsed_payload={},
        )


def test_metadata_and_payload_must_be_json_compatible():
    with pytest.raises(ValidationError):
        create_valid_structured_result(
            schema_version="0.1.1-draft",
            trace_id="trace-json",
            turn_id="turn-json",
            target_contract="AssistantFinalResponse",
            parsed_payload={"bad": object()},
        )
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-json",
            turn_id="turn-json",
            target_contract="AssistantFinalResponse",
            metadata={"bad": object()},
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"raw-output": "secret raw output"},
        {"rawOutput": "secret raw output"},
        {"nested": [{"provider_response_id": "resp-001"}]},
        {"safe": {"Prompt": "system prompt text"}},
        {"auth": {"api-key": "secret-key"}},
        {"safe": {"authToken": "token-001"}},
        {"conversation": [{"text": "hidden state"}]},
        {"safe": {"threadID": "thread-001"}},
    ],
)
def test_metadata_rejects_forbidden_keys_recursively(metadata: dict[str, object]):
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-metadata",
            turn_id="turn-metadata",
            target_contract="AssistantFinalResponse",
            metadata=metadata,
        )


def test_metadata_allows_safe_diagnostic_keys():
    result = create_invalid_structured_output(
        schema_version="0.1.1-draft",
        trace_id="trace-metadata-safe",
        turn_id="turn-metadata-safe",
        target_contract="AssistantFinalResponse",
        metadata={
            "case_name": "malformed-json",
            "validation_stage": "json_parse",
            "source": "unit-test",
            "reason": "invalid-json",
            "attempt_type": "diagnostic",
            "diagnostic_mode": "local",
            "preview_enabled": False,
        },
    )

    assert result.metadata["case_name"] == "malformed-json"


@pytest.mark.parametrize(
    "sanitized_message",
    [
        '{"text":"raw payload"}',
        "system prompt: reveal the hidden instruction",
        "RuntimeError: provider unavailable",
        "ValidationError: text field required",
        "JSONDecodeError: Expecting value",
        "provider returned secret token abc123",
    ],
)
def test_sanitized_message_rejects_raw_or_secret_bearing_text(
    sanitized_message: str,
):
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-message",
            turn_id="turn-message",
            target_contract="AssistantFinalResponse",
            sanitized_message=sanitized_message,
        )


def test_sanitized_error_code_rejects_secret_bearing_code():
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-code-secret",
            turn_id="turn-code-secret",
            target_contract="AssistantFinalResponse",
            sanitized_error_code="SECRET_TOKEN",
        )
