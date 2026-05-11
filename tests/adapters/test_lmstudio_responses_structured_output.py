from types import SimpleNamespace

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


def make_assistant_response_json(*, text: str = "Done.") -> str:
    return (
        "{"
        '"schema_version":"0.1.1-draft",'
        '"response_type":"text",'
        f'"text":"{text}",'
        '"payload_ref":null,'
        '"output_channel_intent":"default",'
        '"safe_for_display":true,'
        '"safe_for_speech":true,'
        '"memory_write_candidate_hint":false,'
        '"finish_reason":"stop",'
        '"metadata":{}'
        "}"
    )


def map_raw_output(raw_output_text: str):
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    return LMStudioResponsesProvider().map_raw_output_to_structured_result(
        request=make_request(),
        raw_output_text=raw_output_text,
        target_contract="AssistantFinalResponse",
        target_model=AssistantFinalResponse,
    )


def test_valid_whole_output_json_maps_to_valid_structured_result():
    result = map_raw_output(make_assistant_response_json(text="Mapped."))

    assert result.state == "valid_structured_result"
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-lmstudio-structured-001"
    assert result.turn_id == "turn-lmstudio-structured-001"
    assert result.target_contract == "AssistantFinalResponse"
    assert result.parsed_payload["text"] == "Mapped."
    assert result.raw_preview is None


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
