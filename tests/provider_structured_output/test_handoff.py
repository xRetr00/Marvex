from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.provider_structured_output.fallback_result import (
    StructuredOutputFallbackResult,
    create_incomplete_unresolved,
    create_invalid_structured_output,
    create_provider_error,
    create_provider_timeout,
    create_refusal_unresolved,
    create_valid_structured_result,
)
from packages.provider_structured_output.handoff import (
    StructuredOutputHandoffDraft,
    build_structured_output_handoff_draft,
)


PACKAGE_ROOT = Path("packages/provider_structured_output")
RAW_OUTPUT = '{"text":"raw provider output","api_key":"secret"}'
PAYLOAD = {"schema_version": "0.1.1-draft", "text": "Done.", "metadata": {}}


def valid_result(**overrides: object) -> StructuredOutputFallbackResult:
    values = {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-handoff",
        "turn_id": "turn-handoff",
        "target_contract": "AssistantFinalResponse",
        "parsed_payload": PAYLOAD,
    }
    values.update(overrides)
    return create_valid_structured_result(**values)


STATE_CASES = [
    (
        create_invalid_structured_output,
        "invalid_structured_output",
        "invalid_structured_payload",
    ),
    (create_provider_error, "provider_error", "provider_error"),
    (create_provider_timeout, "provider_timeout", "provider_timeout"),
    (
        create_refusal_unresolved,
        "refusal_unresolved_or_provider_specific",
        "refusal_unresolved",
    ),
    (
        create_incomplete_unresolved,
        "incomplete_unresolved_or_provider_specific",
        "incomplete_unresolved",
    ),
]


def build_non_valid_result(factory):
    return factory(
        schema_version="0.1.1-draft",
        trace_id="trace-non-valid",
        turn_id="turn-non-valid",
        target_contract="AssistantFinalResponse",
    )


def test_valid_fallback_result_builds_usable_handoff_draft():
    draft = build_structured_output_handoff_draft(valid_result())

    assert isinstance(draft, StructuredOutputHandoffDraft)
    assert draft.handoff_status == "usable_structured_payload"
    assert draft.state == "valid_structured_result"
    assert draft.schema_version == "0.1.1-draft"
    assert draft.trace_id == "trace-handoff"
    assert draft.turn_id == "turn-handoff"
    assert draft.target_contract == "AssistantFinalResponse"
    assert draft.parsed_payload == PAYLOAD
    assert draft.safe_for_user_facing_final_response is False
    assert draft.diagnostic_only is False
    assert draft.raw_preview is None


@pytest.mark.parametrize(("factory", "state", "status"), STATE_CASES)
def test_non_valid_fallback_states_map_deterministically(factory, state, status):
    draft = build_structured_output_handoff_draft(build_non_valid_result(factory))

    assert draft.state == state
    assert draft.handoff_status == status
    assert draft.parsed_payload is None
    assert draft.trace_id == "trace-non-valid"
    assert draft.turn_id == "turn-non-valid"


def test_parsed_payload_appears_only_for_valid_structured_result():
    valid_draft = build_structured_output_handoff_draft(valid_result())
    invalid_draft = build_structured_output_handoff_draft(
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-invalid",
            turn_id="turn-invalid",
            target_contract="AssistantFinalResponse",
        )
    )

    assert valid_draft.parsed_payload == PAYLOAD
    assert invalid_draft.parsed_payload is None


def test_unknown_future_state_fails_closed_if_validation_is_bypassed():
    result = StructuredOutputFallbackResult.model_construct(
        schema_version="0.1.1-draft",
        trace_id="trace-future",
        turn_id="turn-future",
        state="future_state",
        target_contract="AssistantFinalResponse",
        sanitized_message="Structured output was invalid.",
        sanitized_error_code="INVALID_STRUCTURED_OUTPUT",
        parsed_payload=None,
        raw_preview=None,
        metadata={},
    )

    with pytest.raises(ValueError, match="unsupported structured output state"):
        build_structured_output_handoff_draft(result)


def test_handoff_rechecks_valid_payload_json_compatibility_and_forbidden_keys():
    non_json_result = StructuredOutputFallbackResult.model_construct(
        schema_version="0.1.1-draft",
        trace_id="trace-non-json",
        turn_id="turn-non-json",
        state="valid_structured_result",
        target_contract="AssistantFinalResponse",
        sanitized_message="Structured output validated.",
        sanitized_error_code=None,
        parsed_payload={"bad": object()},
        raw_preview=None,
        metadata={},
    )
    forbidden_key_result = StructuredOutputFallbackResult.model_construct(
        schema_version="0.1.1-draft",
        trace_id="trace-forbidden-key",
        turn_id="turn-forbidden-key",
        state="valid_structured_result",
        target_contract="AssistantFinalResponse",
        sanitized_message="Structured output validated.",
        sanitized_error_code=None,
        parsed_payload={"metadata": {"authToken": "token-001"}},
        raw_preview=None,
        metadata={},
    )

    with pytest.raises(ValidationError):
        build_structured_output_handoff_draft(non_json_result)
    with pytest.raises(ValidationError):
        build_structured_output_handoff_draft(forbidden_key_result)


def test_handoff_rechecks_sanitized_message_and_error_code():
    with pytest.raises(ValidationError):
        StructuredOutputHandoffDraft(
            schema_version="0.1.1-draft",
            trace_id="trace-message",
            turn_id="turn-message",
            state="invalid_structured_output",
            target_contract="AssistantFinalResponse",
            handoff_status="invalid_structured_payload",
            sanitized_message="system prompt: leak this",
            sanitized_error_code="INVALID_STRUCTURED_OUTPUT",
            parsed_payload=None,
            raw_preview=None,
            diagnostic_only=False,
            safe_for_user_facing_final_response=False,
        )
    with pytest.raises(ValidationError):
        StructuredOutputHandoffDraft(
            schema_version="0.1.1-draft",
            trace_id="trace-code",
            turn_id="turn-code",
            state="invalid_structured_output",
            target_contract="AssistantFinalResponse",
            handoff_status="invalid_structured_payload",
            sanitized_message="Structured output was invalid.",
            sanitized_error_code="SECRET_TOKEN",
            parsed_payload=None,
            raw_preview=None,
            diagnostic_only=False,
            safe_for_user_facing_final_response=False,
        )


def test_raw_preview_is_null_by_default_and_preview_drafts_are_diagnostic_only():
    default_draft = build_structured_output_handoff_draft(
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-preview-default",
            turn_id="turn-preview-default",
            target_contract="AssistantFinalResponse",
        )
    )
    preview_draft = build_structured_output_handoff_draft(
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-preview",
            turn_id="turn-preview",
            target_contract="AssistantFinalResponse",
            raw_preview="x" * 300,
        )
    )

    assert default_draft.raw_preview is None
    assert default_draft.diagnostic_only is False
    assert preview_draft.raw_preview == "x" * 300
    assert preview_draft.diagnostic_only is True


def test_raw_output_and_sensitive_terms_are_not_in_handoff_message_or_dump():
    draft = build_structured_output_handoff_draft(
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-leak",
            turn_id="turn-leak",
            target_contract="AssistantFinalResponse",
            sanitized_error_code="INVALID_JSON",
            sanitized_message="Structured output was not valid JSON.",
        )
    )
    dumped = draft.model_dump()

    assert RAW_OUTPUT not in str(dumped)
    for leaked in [
        "system prompt",
        "secret",
        "token",
        "provider response",
        "session",
        "thread",
        "ValidationError",
        "JSONDecodeError",
    ]:
        assert leaked not in draft.sanitized_message


def test_safe_metadata_is_excluded_and_unsafe_metadata_is_rejected_upstream():
    result = create_invalid_structured_output(
        schema_version="0.1.1-draft",
        trace_id="trace-metadata",
        turn_id="turn-metadata",
        target_contract="AssistantFinalResponse",
        metadata={"case_name": "safe-diagnostic"},
    )
    draft = build_structured_output_handoff_draft(result)

    assert "metadata" not in draft.model_dump()
    with pytest.raises(ValidationError):
        create_invalid_structured_output(
            schema_version="0.1.1-draft",
            trace_id="trace-unsafe-metadata",
            turn_id="turn-unsafe-metadata",
            target_contract="AssistantFinalResponse",
            metadata={"session_id": "hidden"},
        )


def test_unknown_handoff_fields_are_rejected():
    with pytest.raises(ValidationError):
        StructuredOutputHandoffDraft(
            schema_version="0.1.1-draft",
            trace_id="trace-extra",
            turn_id="turn-extra",
            state="invalid_structured_output",
            target_contract="AssistantFinalResponse",
            handoff_status="invalid_structured_payload",
            sanitized_message="Structured output was invalid.",
            sanitized_error_code="INVALID_STRUCTURED_OUTPUT",
            parsed_payload=None,
            raw_preview=None,
            diagnostic_only=False,
            safe_for_user_facing_final_response=False,
            raw_provider_output="secret",
        )


def test_package_root_does_not_export_handoff_draft():
    import packages.provider_structured_output as package_root

    assert not hasattr(package_root, "StructuredOutputHandoffDraft")
    assert not hasattr(package_root, "build_structured_output_handoff_draft")


def test_handoff_module_imports_no_forbidden_runtime_boundaries():
    source = (PACKAGE_ROOT / "handoff.py").read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.assistant_runtime",
        "packages.provider_runtime",
        "packages.adapters",
        "packages.ports",
        "packages.contracts",
        "apps.cli",
        "services",
        "ProviderResponse",
        "AssistantTurnResult",
        "json.loads",
        "retry",
        "render_prompt",
    ]

    assert [term for term in forbidden if term in source] == []
