import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from packages.contracts import AssistantFinalResponse, ProviderRequest, ProviderResponse


def make_request() -> ProviderRequest:
    return ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-lmstudio-structured-001",
        turn_id="turn-lmstudio-structured-001",
        model="openai/gpt-oss-20b",
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
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    return LMStudioResponsesProvider().map_raw_output_to_structured_result(
        request=make_request(),
        raw_output_text=raw_output_text,
        target_contract="AssistantFinalResponse",
        target_model=AssistantFinalResponse,
        include_raw_preview=include_raw_preview,
    )


def assert_lmstudio_context_preserved(result: object) -> None:
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-lmstudio-structured-001"
    assert result.turn_id == "turn-lmstudio-structured-001"
    assert result.target_contract == "AssistantFinalResponse"


def test_valid_whole_output_json_maps_to_valid_structured_result():
    result = map_raw_output(make_assistant_response_json(text="Mapped."))

    assert result.state == "valid_structured_result"
    assert_lmstudio_context_preserved(result)
    assert result.parsed_payload["text"] == "Mapped."
    assert result.raw_preview is None


def test_valid_whole_output_json_with_extra_fields_follows_target_model_behavior():
    raw_output_text = json.dumps(
        make_assistant_response_payload(extra_provider_field="ignored?")
    )

    result = map_raw_output(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert_lmstudio_context_preserved(result)
    assert result.sanitized_error_code == "VALIDATION_FAILED"
    assert raw_output_text not in result.sanitized_message


@pytest.mark.parametrize(
    ("raw_output_text", "error_code"),
    [
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
    ],
)
def test_lmstudio_pressure_matrix_invalid_outputs(
    raw_output_text: str,
    error_code: str,
):
    result = map_raw_output(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert_lmstudio_context_preserved(result)
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


def test_malformed_json_maps_to_invalid_structured_output():
    result = map_raw_output('{"text": "unterminated"')

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "INVALID_JSON"
    assert result.parsed_payload is None
    assert result.raw_preview is None


def test_prose_wrapped_json_is_rejected():
    result = map_raw_output(f"Here is JSON: {make_assistant_response_json()}")

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "INVALID_JSON"
    assert result.parsed_payload is None


def test_raw_output_and_pydantic_error_text_are_not_copied_to_sanitized_message():
    raw_output_text = make_assistant_response_json(text="")

    result = map_raw_output(raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_message == "Structured output failed target validation."
    assert raw_output_text not in result.sanitized_message
    assert "text" not in result.sanitized_message
    assert result.raw_preview is None


def test_lmstudio_hook_inherits_metadata_hardening():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    result = LMStudioResponsesProvider().map_raw_output_to_structured_result(
        request=make_request(),
        raw_output_text=make_assistant_response_json(text="Mapped."),
        target_contract="AssistantFinalResponse",
        target_model=AssistantFinalResponse,
    )

    with pytest.raises(ValidationError):
        type(result).model_validate(
            result.model_dump() | {"metadata": {"rawResponse": "hidden raw data"}}
        )


class RecordingResponses:
    def __init__(self, response: object) -> None:
        self.calls: list[dict[str, object]] = []
        self._response = response

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class RecordingClient:
    def __init__(self, response: object) -> None:
        self.responses = RecordingResponses(response)


class RecordingClientFactory:
    def __init__(self, client: RecordingClient) -> None:
        self.client = client

    def __call__(self, **kwargs):
        return self.client


def test_normal_send_response_shape_is_unchanged_for_json_output_text():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    raw_output_text = make_assistant_response_json(text="Still raw.")
    client = RecordingClient(
        SimpleNamespace(
            id="resp-structured-001",
            output_text=raw_output_text,
            usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            status="completed",
        )
    )
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    response = provider.send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.response_id == "resp-structured-001"
    assert validated.output_text == raw_output_text
    assert validated.error is None
    assert "structured_payload" not in validated.model_dump()
