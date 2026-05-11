from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field, ValidationError

from packages.provider_structured_output import (
    StructuredOutputFallbackResult,
    validate_raw_structured_output,
)


class DemoPayload(BaseModel):
    text: str = Field(..., min_length=1)
    count: int


def _map(raw_output_text: str, *, include_raw_preview: bool = False):
    return validate_raw_structured_output(
        schema_version="0.1.1-draft",
        trace_id="trace-raw-001",
        turn_id="turn-raw-001",
        target_contract="DemoPayload",
        raw_output_text=raw_output_text,
        target_model=DemoPayload,
        include_raw_preview=include_raw_preview,
    )


def test_valid_whole_output_json_validates_into_parsed_payload():
    result = _map('{"text": "Done.", "count": 2}')

    assert result.state == "valid_structured_result"
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-raw-001"
    assert result.turn_id == "turn-raw-001"
    assert result.target_contract == "DemoPayload"
    assert result.parsed_payload == {"text": "Done.", "count": 2}
    assert result.raw_preview is None
    assert result.sanitized_error_code is None


@pytest.mark.parametrize(
    ("raw_output_text", "error_code"),
    [
        ("", "EMPTY_STRUCTURED_OUTPUT"),
        ("   \r\n\t", "EMPTY_STRUCTURED_OUTPUT"),
        ('{"text": "unterminated"', "INVALID_JSON"),
        ('Here is JSON: {"text": "Done.", "count": 2}', "INVALID_JSON"),
        ('prefix {"text": "Done.", "count": 2} suffix', "INVALID_JSON"),
    ],
)
def test_invalid_raw_output_maps_to_invalid_structured_output(
    raw_output_text: str,
    error_code: str,
):
    result = _map(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.parsed_payload is None
    assert result.raw_preview is None
    assert result.sanitized_error_code == error_code


def test_valid_json_with_wrong_schema_maps_to_invalid_structured_output():
    result = _map('{"text": "", "count": "not-int"}')

    assert result.state == "invalid_structured_output"
    assert result.parsed_payload is None
    assert result.raw_preview is None
    assert result.sanitized_error_code == "VALIDATION_FAILED"


def test_pydantic_exception_text_is_not_copied_to_sanitized_message():
    result = _map('{"text": "", "count": "secret-invalid-value"}')

    assert result.sanitized_message == "Structured output failed target validation."
    assert "secret-invalid-value" not in result.sanitized_message
    assert "count" not in result.sanitized_message


def test_raw_provider_output_is_not_copied_to_sanitized_message():
    raw_output_text = "secret raw provider text"
    result = _map(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert raw_output_text not in result.sanitized_message


def test_opt_in_raw_preview_is_bounded_to_300_chars():
    raw_output_text = "x" * 350
    result = _map(raw_output_text, include_raw_preview=True)

    assert result.raw_preview == "x" * 300


def test_raw_preview_is_null_by_default_for_all_invalid_output_classes():
    malformed = _map("secret malformed text")
    schema_invalid = _map('{"text": "Done."}')

    assert malformed.raw_preview is None
    assert schema_invalid.raw_preview is None


def test_unknown_fields_in_fallback_result_remain_rejected():
    with pytest.raises(ValidationError):
        StructuredOutputFallbackResult(
            schema_version="0.1.1-draft",
            trace_id="trace-extra",
            turn_id="turn-extra",
            state="valid_structured_result",
            target_contract="DemoPayload",
            sanitized_message="Structured output validated.",
            sanitized_error_code=None,
            parsed_payload={"text": "Done.", "count": 2},
            raw_preview=None,
            metadata={},
            raw_provider_output="secret",
        )


def test_valid_json_must_be_whole_output_not_brace_scraped():
    embedded_json = json.dumps({"text": "Done.", "count": 2})

    result = _map(f"```json\n{embedded_json}\n```")

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "INVALID_JSON"
    assert result.parsed_payload is None
