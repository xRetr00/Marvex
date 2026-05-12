from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.assistant_runtime.structured_output_consumer import (
    AssistantStructuredOutputConsumptionDraft,
    AssistantStructuredOutputInputDraft,
    consume_structured_output_handoff_draft,
)


VALID_PAYLOAD = {
    "schema_version": "0.1.1-draft",
    "text": "Done.",
    "metadata": {"case_name": "accepted"},
}


def input_draft(**overrides: object) -> AssistantStructuredOutputInputDraft:
    values = {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-assistant-structured",
        "turn_id": "turn-assistant-structured",
        "source_state": "valid_structured_result",
        "handoff_status": "usable_structured_payload",
        "target_contract": "AssistantFinalResponse",
        "sanitized_message": "Structured output validated.",
        "sanitized_error_code": None,
        "parsed_payload": VALID_PAYLOAD,
        "diagnostic_only": False,
        "metadata": {"case_name": "safe"},
    }
    values.update(overrides)
    return AssistantStructuredOutputInputDraft(**values)


def test_valid_usable_handoff_like_input_maps_to_accepted_future_stage():
    consumed = consume_structured_output_handoff_draft(input_draft())

    assert isinstance(consumed, AssistantStructuredOutputConsumptionDraft)
    assert consumed.consumption_status == "accepted_for_future_stage"
    assert consumed.schema_version == "0.1.1-draft"
    assert consumed.trace_id == "trace-assistant-structured"
    assert consumed.turn_id == "turn-assistant-structured"
    assert consumed.source_state == "valid_structured_result"
    assert consumed.handoff_status == "usable_structured_payload"
    assert consumed.target_contract == "AssistantFinalResponse"
    assert consumed.parsed_payload == VALID_PAYLOAD
    assert consumed.safe_for_user_facing_final_response is False


@pytest.mark.parametrize(
    ("handoff_status", "expected"),
    [
        ("invalid_structured_payload", "rejected_invalid_structured_payload"),
        ("provider_error", "rejected_provider_error"),
        ("provider_timeout", "rejected_provider_timeout"),
        ("refusal_unresolved", "rejected_refusal_unresolved"),
        ("incomplete_unresolved", "rejected_incomplete_unresolved"),
    ],
)
def test_non_usable_handoff_statuses_map_to_rejected_consumption_statuses(
    handoff_status, expected
):
    consumed = consume_structured_output_handoff_draft(
        input_draft(
            source_state=f"{handoff_status}_source",
            handoff_status=handoff_status,
            sanitized_message="Structured output is not usable.",
            sanitized_error_code="STRUCTURED_OUTPUT_NOT_USABLE",
            parsed_payload=None,
        )
    )

    assert consumed.consumption_status == expected
    assert consumed.parsed_payload is None
    assert consumed.trace_id == "trace-assistant-structured"
    assert consumed.turn_id == "turn-assistant-structured"


def test_unknown_future_handoff_status_fails_closed():
    draft = input_draft(handoff_status="future_status", parsed_payload=None)

    with pytest.raises(ValueError, match="unsupported structured output status"):
        consume_structured_output_handoff_draft(draft)


def test_parsed_payload_is_retained_only_for_accepted_status():
    accepted = consume_structured_output_handoff_draft(input_draft())
    rejected = consume_structured_output_handoff_draft(
        input_draft(
            handoff_status="invalid_structured_payload",
            source_state="invalid_structured_output",
            sanitized_error_code="INVALID_STRUCTURED_OUTPUT",
            sanitized_message="Structured output is not usable.",
            parsed_payload=None,
        )
    )

    assert accepted.parsed_payload == VALID_PAYLOAD
    assert rejected.parsed_payload is None


def test_non_accepted_status_rejects_parsed_payload():
    with pytest.raises(ValidationError):
        input_draft(
            handoff_status="provider_error",
            source_state="provider_error",
            sanitized_error_code="PROVIDER_ERROR",
            sanitized_message="Provider could not return structured output.",
            parsed_payload=VALID_PAYLOAD,
        )


def test_diagnostic_only_input_cannot_become_accepted_usable_data():
    draft = input_draft(diagnostic_only=True)

    with pytest.raises(ValueError, match="diagnostic"):
        consume_structured_output_handoff_draft(draft)


@pytest.mark.parametrize(
    "field",
    ["schema_version", "trace_id", "turn_id", "source_state", "target_contract"],
)
def test_identity_fields_reject_empty_values(field):
    with pytest.raises(ValidationError):
        input_draft(**{field: "   "})


@pytest.mark.parametrize(
    "metadata",
    [
        {"rawOutput": "raw provider output"},
        {"nested": [{"system-prompt": "ignore instructions"}]},
        {"conversation": {"thread_id": "thread-001"}},
        {"auth": {"bearerToken": "secret-token"}},
    ],
)
def test_unsafe_metadata_keys_are_rejected_recursively(metadata):
    with pytest.raises(ValidationError):
        input_draft(metadata=metadata)


@pytest.mark.parametrize(
    "payload",
    [
        {"raw_provider_output": "raw provider output"},
        {"messages": [{"content": "prompt-like text"}]},
        {"metadata": {"provider_response_id": "resp-001"}},
        {"auth": {"api-key": "secret"}},
    ],
)
def test_unsafe_parsed_payload_keys_are_rejected_recursively(payload):
    with pytest.raises(ValidationError):
        input_draft(parsed_payload=payload)


@pytest.mark.parametrize(
    "message",
    [
        '{"text":"full raw payload"}',
        "system prompt: do this",
        "api_key secret-token",
        "provider response id resp-001",
        "session id session-001",
        "thread id thread-001",
        "ValidationError field required",
        "JSONDecodeError line 1 column 2",
    ],
)
def test_sanitized_message_rejects_leakage_terms(message):
    with pytest.raises(ValidationError):
        input_draft(
            handoff_status="invalid_structured_payload",
            source_state="invalid_structured_output",
            sanitized_error_code="INVALID_STRUCTURED_OUTPUT",
            sanitized_message=message,
            parsed_payload=None,
        )


@pytest.mark.parametrize(
    "error_code",
    ["", "invalid-json", "SECRET_TOKEN", "API_KEY_LEAK", "BEARER_AUTH"],
)
def test_sanitized_error_code_is_stable_and_non_secret_bearing(error_code):
    with pytest.raises(ValidationError):
        input_draft(
            handoff_status="invalid_structured_payload",
            source_state="invalid_structured_output",
            sanitized_message="Structured output is not usable.",
            sanitized_error_code=error_code,
            parsed_payload=None,
        )


def test_unknown_top_level_fields_and_raw_preview_are_rejected():
    with pytest.raises(ValidationError):
        AssistantStructuredOutputInputDraft(
            **input_draft().model_dump(),
            raw_preview="raw provider output",
        )


def test_consumption_draft_never_creates_final_response_or_turn_result():
    consumed = consume_structured_output_handoff_draft(input_draft())
    dumped = consumed.model_dump()

    assert consumed.safe_for_user_facing_final_response is False
    assert "assistant_final_response" not in dumped
    assert "AssistantTurnResult" not in str(dumped)


def test_consumption_draft_direct_construction_rechecks_safety_fields():
    safe = consume_structured_output_handoff_draft(input_draft()).model_dump()

    with pytest.raises(ValidationError):
        AssistantStructuredOutputConsumptionDraft(
            **{**safe, "sanitized_message": "secret token leaked"}
        )
    with pytest.raises(ValidationError):
        AssistantStructuredOutputConsumptionDraft(
            **{**safe, "parsed_payload": {"metadata": {"thread_id": "thread-001"}}}
        )
    with pytest.raises(ValidationError):
        AssistantStructuredOutputConsumptionDraft(
            **{**safe, "metadata": {"raw_output": "raw provider output"}}
        )


def test_structured_output_consumer_imports_no_forbidden_boundaries():
    source = Path(
        "packages/assistant_runtime/structured_output_consumer.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.provider_runtime",
        "packages.adapters",
        "packages.provider_structured_output",
        "packages.ports",
        "packages.contracts",
        "apps.cli",
        "services",
        "ProviderRuntime",
        "ProviderResponse",
        "AssistantTurnResult",
        "AssistantFinalResponse(",
        "json.loads",
        "retry",
        "render_prompt",
    ]

    assert [term for term in forbidden if term in source] == []


def test_package_root_does_not_export_structured_output_consumer_seam():
    import packages.assistant_runtime as package_root

    assert not hasattr(package_root, "AssistantStructuredOutputInputDraft")
    assert not hasattr(package_root, "AssistantStructuredOutputConsumptionDraft")
    assert not hasattr(package_root, "consume_structured_output_handoff_draft")
