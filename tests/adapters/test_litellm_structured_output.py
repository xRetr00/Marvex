import json
from types import SimpleNamespace

from packages.contracts import AssistantFinalResponse, ProviderRequest, ProviderResponse


def make_request() -> ProviderRequest:
    return ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-litellm-structured-001",
        turn_id="turn-litellm-structured-001",
        model="openrouter/test-model",
        input_text="Return structured JSON.",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )


def make_assistant_response_payload(**overrides: object) -> dict[str, object]:
    payload = {
        "schema_version": "0.1.1-draft",
        "response_type": "text",
        "text": "Done.",
        "payload_ref": None,
        "output_channel_intent": "default",
        "safe_for_display": True,
        "safe_for_speech": True,
        "memory_write_candidate_hint": False,
        "finish_reason": "stop",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def make_assistant_response_json(*, text: str = "Done.") -> str:
    return json.dumps(make_assistant_response_payload(text=text))


def map_raw_output(raw_output_text: str, *, include_raw_preview: bool = False):
    from packages.adapters.providers.litellm import LiteLLMProvider

    return LiteLLMProvider().map_raw_output_to_structured_result(
        request=make_request(),
        raw_output_text=raw_output_text,
        target_contract="AssistantFinalResponse",
        target_model=AssistantFinalResponse,
        include_raw_preview=include_raw_preview,
    )


def assert_litellm_context_preserved(result: object) -> None:
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-litellm-structured-001"
    assert result.turn_id == "turn-litellm-structured-001"
    assert result.target_contract == "AssistantFinalResponse"


def test_valid_whole_output_json_maps_to_valid_structured_result():
    result = map_raw_output(make_assistant_response_json(text="Mapped."))

    assert result.state == "valid_structured_result"
    assert_litellm_context_preserved(result)
    assert result.parsed_payload["text"] == "Mapped."
    assert result.raw_preview is None


def test_valid_whole_output_json_with_extra_fields_follows_target_model_behavior():
    raw_output_text = json.dumps(
        make_assistant_response_payload(extra_provider_field="ignored?")
    )

    result = map_raw_output(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert_litellm_context_preserved(result)
    assert result.sanitized_error_code == "VALIDATION_FAILED"
    assert raw_output_text not in result.sanitized_message


INVALID_CASES = [
    (
        json.dumps(make_assistant_response_payload(text={"not": "a string"})),
        "VALIDATION_FAILED",
    ),
    (json.dumps([make_assistant_response_payload()]), "VALIDATION_FAILED"),
    ("", "EMPTY_STRUCTURED_OUTPUT"),
    ("   \r\n\t", "EMPTY_STRUCTURED_OUTPUT"),
    ('{"schema_version": "0.1.1-draft"', "INVALID_JSON"),
    (f"Here is JSON: {make_assistant_response_json()}", "INVALID_JSON"),
    (f"```json\n{make_assistant_response_json()}\n```", "INVALID_JSON"),
    (
        json.dumps(make_assistant_response_payload(prompt="system prompt")),
        "VALIDATION_FAILED",
    ),
    (
        json.dumps(make_assistant_response_payload(raw_output="raw text")),
        "VALIDATION_FAILED",
    ),
    (
        json.dumps(
            make_assistant_response_payload(
                metadata={"provider_response_id": "resp-001"}
            )
        ),
        "VALIDATION_FAILED",
    ),
    (
        json.dumps(
            make_assistant_response_payload(
                metadata={"session_id": "sess-001", "thread_id": "thread-001"}
            )
        ),
        "VALIDATION_FAILED",
    ),
    (
        json.dumps(
            make_assistant_response_payload(
                metadata={"authToken": "token-001", "api_key": "key-001"}
            )
        ),
        "VALIDATION_FAILED",
    ),
]


def test_pressure_matrix_invalid_outputs():
    for raw_output_text, error_code in INVALID_CASES:
        result = map_raw_output(raw_output_text)

        assert result.state == "invalid_structured_output"
        assert_litellm_context_preserved(result)
        assert result.sanitized_error_code == error_code
        assert result.parsed_payload is None
        assert result.raw_preview is None
        if raw_output_text:
            assert raw_output_text not in result.sanitized_message
        for leaked in [
            "system prompt",
            "raw text",
            "resp-001",
            "sess-001",
            "thread-001",
            "token-001",
            "api_key",
            "ValidationError",
            "JSONDecodeError",
        ]:
            assert leaked not in result.sanitized_message


def test_very_long_raw_output_preview_is_disabled_by_default():
    raw_output_text = "x" * 1000

    result = map_raw_output(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "INVALID_JSON"
    assert result.raw_preview is None
    assert raw_output_text not in result.sanitized_message


def test_very_long_raw_output_preview_is_bounded_when_enabled():
    raw_output_text = "x" * 1000

    result = map_raw_output(raw_output_text, include_raw_preview=True)

    assert result.state == "invalid_structured_output"
    assert result.raw_preview == "x" * 300


def test_raw_output_and_exception_details_are_not_copied_to_sanitized_message():
    raw_output_text = make_assistant_response_json(text="")

    result = map_raw_output(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_message == "Structured output failed target validation."
    assert raw_output_text not in result.sanitized_message
    assert "text" not in result.sanitized_message
    assert result.raw_preview is None


def test_normal_send_response_shape_is_unchanged_for_json_output_text(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, litellm_provider

    raw_output_text = make_assistant_response_json(text="Still raw.")
    response_payload = SimpleNamespace(
        id="litellm-structured-001",
        status="completed",
        output_text=raw_output_text,
        output=[],
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    )

    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kwargs: response_payload,
    )

    response = LiteLLMProvider().send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.response_id == "litellm-structured-001"
    assert validated.output_text == raw_output_text
    assert validated.error is None
    assert "structured_payload" not in validated.model_dump()
