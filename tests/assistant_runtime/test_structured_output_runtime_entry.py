from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.assistant_runtime.runtime import AssistantTurnRuntime
from packages.assistant_runtime.structured_output_consumer import (
    AssistantStructuredOutputInputDraft,
)
from packages.assistant_runtime.structured_output_runtime_entry import (
    consume_structured_output_for_future_stage,
)
from packages.provider_structured_output.fallback_result import (
    create_incomplete_unresolved,
    create_invalid_structured_output,
    create_provider_error,
    create_provider_timeout,
    create_refusal_unresolved,
    create_valid_structured_result,
)
from packages.provider_structured_output.handoff import (
    build_structured_output_handoff_draft,
)


PAYLOAD = {
    "schema_version": "0.1.1-draft",
    "text": "Done.",
    "metadata": {"case_name": "compatibility"},
}


def provider_draft_dict(result, **overrides: object) -> dict[str, object]:
    draft = build_structured_output_handoff_draft(result)
    data = draft.model_dump(exclude_none=True, exclude_defaults=True)
    data.update(overrides)
    return data


def valid_provider_result(**overrides: object):
    values = {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-compat",
        "turn_id": "turn-compat",
        "target_contract": "AssistantFinalResponse",
        "parsed_payload": PAYLOAD,
    }
    values.update(overrides)
    return create_valid_structured_result(**values)


def non_valid_provider_result(factory):
    return factory(
        schema_version="0.1.1-draft",
        trace_id="trace-compat",
        turn_id="turn-compat",
        target_contract="AssistantFinalResponse",
    )


def test_provider_handoff_dict_maps_to_assistant_accepted_future_stage():
    consumed = consume_structured_output_for_future_stage(
        provider_draft_dict(valid_provider_result())
    )

    assert consumed.consumption_status == "accepted_for_future_stage"
    assert consumed.schema_version == "0.1.1-draft"
    assert consumed.trace_id == "trace-compat"
    assert consumed.turn_id == "turn-compat"
    assert consumed.source_state == "valid_structured_result"
    assert consumed.handoff_status == "usable_structured_payload"
    assert consumed.target_contract == "AssistantFinalResponse"
    assert consumed.parsed_payload == PAYLOAD
    assert consumed.safe_for_user_facing_final_response is False


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        (create_invalid_structured_output, "rejected_invalid_structured_payload"),
        (create_provider_error, "rejected_provider_error"),
        (create_provider_timeout, "rejected_provider_timeout"),
        (create_refusal_unresolved, "rejected_refusal_unresolved"),
        (create_incomplete_unresolved, "rejected_incomplete_unresolved"),
    ],
)
def test_provider_handoff_non_valid_statuses_map_to_assistant_rejections(
    factory, expected
):
    consumed = consume_structured_output_for_future_stage(
        provider_draft_dict(non_valid_provider_result(factory))
    )

    assert consumed.consumption_status == expected
    assert consumed.trace_id == "trace-compat"
    assert consumed.turn_id == "turn-compat"
    assert consumed.parsed_payload is None


def test_entry_accepts_assistant_input_draft_directly():
    draft = AssistantStructuredOutputInputDraft(
        schema_version="0.1.1-draft",
        trace_id="trace-direct",
        turn_id="turn-direct",
        source_state="valid_structured_result",
        handoff_status="usable_structured_payload",
        target_contract="AssistantFinalResponse",
        sanitized_message="Structured output validated.",
        sanitized_error_code=None,
        parsed_payload=PAYLOAD,
        diagnostic_only=False,
        metadata={"case_name": "direct"},
    )

    consumed = consume_structured_output_for_future_stage(draft)

    assert consumed.consumption_status == "accepted_for_future_stage"
    assert consumed.trace_id == "trace-direct"
    assert consumed.turn_id == "turn-direct"
    assert consumed.parsed_payload == PAYLOAD


def test_diagnostic_only_provider_handoff_dict_cannot_be_accepted():
    data = provider_draft_dict(valid_provider_result(), diagnostic_only=True)

    with pytest.raises(ValueError, match="diagnostic"):
        consume_structured_output_for_future_stage(data)


def test_raw_preview_from_provider_handoff_dict_is_rejected():
    data = provider_draft_dict(valid_provider_result(), raw_preview="raw")

    with pytest.raises(ValidationError):
        consume_structured_output_for_future_stage(data)


def test_unknown_future_handoff_status_fails_closed():
    data = provider_draft_dict(
        valid_provider_result(), handoff_status="future_status", parsed_payload=None
    )

    with pytest.raises(ValueError, match="unsupported structured output status"):
        consume_structured_output_for_future_stage(data)


def test_unknown_top_level_fields_are_rejected():
    data = provider_draft_dict(valid_provider_result(), raw_provider_output="raw")

    with pytest.raises(ValidationError):
        consume_structured_output_for_future_stage(data)


def test_unsafe_metadata_is_rejected_recursively_even_if_added_after_provider_side():
    data = provider_draft_dict(
        valid_provider_result(),
        metadata={"nested": [{"session_id": "session-001"}]},
    )

    with pytest.raises(ValidationError):
        consume_structured_output_for_future_stage(data)


def test_unsafe_payload_is_rejected_recursively_even_if_provider_side_is_bypassed():
    data = provider_draft_dict(
        valid_provider_result(),
        parsed_payload={"metadata": {"api_key": "secret"}},
    )

    with pytest.raises(ValidationError):
        consume_structured_output_for_future_stage(data)


def test_no_raw_prompt_secret_or_provider_identifiers_leak_to_consumption_result():
    consumed = consume_structured_output_for_future_stage(
        provider_draft_dict(
            non_valid_provider_result(create_invalid_structured_output),
            sanitized_message="Structured output was invalid.",
            sanitized_error_code="INVALID_STRUCTURED_OUTPUT",
        )
    )
    dumped = str(consumed.model_dump())

    for forbidden in [
        "raw provider output",
        "system prompt",
        "secret",
        "token",
        "provider response id",
        "session id",
        "thread id",
    ]:
        assert forbidden not in dumped.lower()


def test_entry_does_not_create_turn_result_or_final_response():
    consumed = consume_structured_output_for_future_stage(
        provider_draft_dict(valid_provider_result())
    )
    dumped = consumed.model_dump()

    assert consumed.safe_for_user_facing_final_response is False
    assert "assistant_final_response" not in dumped
    assert "AssistantTurnResult" not in str(dumped)


def test_normal_assistant_runtime_no_provider_path_is_unchanged():
    assert not hasattr(AssistantTurnRuntime, "consume_structured_output_for_future_stage")
    assert "structured_output" not in Path(
        "packages/assistant_runtime/runtime.py"
    ).read_text(encoding="utf-8")


def test_package_root_does_not_export_runtime_entry():
    import packages.assistant_runtime as package_root

    assert not hasattr(package_root, "consume_structured_output_for_future_stage")


def test_structured_output_runtime_entry_imports_no_forbidden_boundaries():
    source = Path(
        "packages/assistant_runtime/structured_output_runtime_entry.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.provider_runtime",
        "packages.provider_structured_output",
        "packages.adapters",
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
