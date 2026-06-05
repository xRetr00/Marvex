from pathlib import Path
from types import SimpleNamespace

from packages.contracts import ErrorCode, FinishReason, ProviderRequest, ProviderResponse
from packages.ports.provider import ProviderPort


def make_request(
    *,
    instructions: str | None = "Follow system guidance.",
    previous_response_id: str | None = "prev-001",
    provider_options: dict[str, object] | None = None,
) -> ProviderRequest:
    return ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        model="openai/gpt-oss-20b",
        input_text="Hello",
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options or {},
    )


def make_response(
    *,
    response_id: str = "resp-001",
    output_text: str | None = "LM Studio output",
    usage: object | None = None,
    status: str | None = None,
    output: object | None = None,
) -> SimpleNamespace:
    value = SimpleNamespace(
        id=response_id,
        usage=usage,
    )
    if output_text is not None:
        value.output_text = output_text
    if status is not None:
        value.status = status
    if output is not None:
        value.output = output
    return value


class RecordingResponses:
    def __init__(self, response: object | None = None, exception: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.cancel_calls: list[str] = []
        self.delete_calls: list[str] = []
        self._response = response or make_response()
        self._exception = exception

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._response

    def cancel(self, response_id: str):
        self.cancel_calls.append(response_id)
        return make_response(response_id=response_id, status="cancelled")

    def delete(self, response_id: str):
        self.delete_calls.append(response_id)
        return {"id": response_id, "object": "response", "deleted": True}


class RecordingClient:
    def __init__(self, response: object | None = None, exception: Exception | None = None) -> None:
        self.responses = RecordingResponses(response=response, exception=exception)


class RecordingClientFactory:
    def __init__(self, client: RecordingClient) -> None:
        self.client = client
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.client


def test_adapter_satisfies_provider_port():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    assert isinstance(LMStudioResponsesProvider(), ProviderPort)


def test_sdk_client_created_with_lmstudio_base_url_and_placeholder_api_key():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    factory = RecordingClientFactory(client)

    LMStudioResponsesProvider(client_factory=factory).send(make_request())

    assert factory.calls == [
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "lm-studio",
        }
    ]


def test_responses_create_receives_model_input_instructions_and_previous_response_id():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    provider.send(make_request())

    assert client.responses.calls == [
        {
            "model": "openai/gpt-oss-20b",
            "input": "Hello",
            "instructions": "Follow system guidance.",
            "previous_response_id": "prev-001",
        }
    ]


def test_instructions_and_previous_response_id_are_omitted_when_none():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    provider.send(make_request(instructions=None, previous_response_id=None))

    assert client.responses.calls == [
        {
            "model": "openai/gpt-oss-20b",
            "input": "Hello",
        }
    ]


def test_no_tools_mcp_stream_or_streaming_fields_sent():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    provider.send(
        make_request(
            provider_options={
                "tools": [{"name": "forbidden"}],
                "mcp": {"server": "forbidden"},
                "stream": True,
                "streaming": True,
            }
        )
    )

    forbidden = {"tools", "mcp", "stream", "streaming"}
    assert forbidden.isdisjoint(client.responses.calls[0])


def test_response_id_output_text_and_usage_are_parsed():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    usage = SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5)
    client = RecordingClient(
        response=make_response(
            response_id="resp-lmstudio",
            output_text="direct output",
            usage=usage,
            status="completed",
        )
    )
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    response = provider.send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.provider_name == "lmstudio_responses"
    assert validated.response_id == "resp-lmstudio"
    assert validated.output_text == "direct output"
    assert validated.usage == {
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
    }
    assert validated.finish_reason == FinishReason.STOP


def test_output_text_fallback_reads_output_content_text():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    output = [
        SimpleNamespace(
            content=[
                SimpleNamespace(type="output_text", text="fallback "),
                {"type": "output_text", "text": "text"},
            ]
        )
    ]
    client = RecordingClient(response=make_response(output_text=None, output=output))
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    response = provider.send(make_request())

    assert response.output_text == "fallback text"


def test_sdk_exception_maps_to_error_envelope():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient(exception=RuntimeError("provider unavailable"))
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    response = provider.send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.output_text == ""
    assert validated.finish_reason == FinishReason.ERROR
    assert validated.error is not None
    assert validated.error.code == ErrorCode.PROVIDER_ERROR
    assert validated.error.message == "provider unavailable"
    assert validated.error.source == "lmstudio_responses_provider"


def test_provider_options_allowlist_and_ignored_options_are_recorded():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    response = provider.send(
        make_request(
            provider_options={
                "temperature": 0.1,
                "max_output_tokens": 64,
                "top_p": 0.9,
                "timeout": 30,
                "parallel_tool_calls": False,
                "api_key": "secret",
                "unknown": True,
            }
        )
    )

    assert client.responses.calls[0]["temperature"] == 0.1
    assert client.responses.calls[0]["max_output_tokens"] == 64
    assert client.responses.calls[0]["top_p"] == 0.9
    assert client.responses.calls[0]["timeout"] == 30
    assert client.responses.calls[0]["parallel_tool_calls"] is False
    assert "api_key" not in client.responses.calls[0]
    assert "unknown" not in client.responses.calls[0]
    assert response.raw_metadata["ignored_provider_options"] == ["api_key", "unknown"]


def test_reasoning_options_are_sent_only_when_configured():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    provider.send(
        make_request(
            provider_options={
                "reasoning_effort": "high",
                "reasoning_summary": "auto",
            }
        )
    )

    assert client.responses.calls[0]["reasoning"] == {"effort": "high", "summary": "auto"}


def test_reasoning_effort_aliases_are_normalized_before_responses_request():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    provider.send(make_request(provider_options={"reasoning_effort": "on"}))

    assert client.responses.calls[0]["reasoning"] == {"effort": "medium"}


def test_response_cancel_and_delete_call_responses_endpoints():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider

    client = RecordingClient()
    provider = LMStudioResponsesProvider(client_factory=RecordingClientFactory(client))

    cancelled = provider.cancel_response("resp-cancel")
    deleted = provider.delete_response("resp-delete")

    assert client.responses.cancel_calls == ["resp-cancel"]
    assert client.responses.delete_calls == ["resp-delete"]
    assert cancelled["id"] == "resp-cancel"
    assert cancelled["status"] == "cancelled"
    assert deleted == {"id": "resp-delete", "object": "response", "deleted": True}


def test_adapter_source_has_no_forbidden_boundary_or_raw_http_imports():
    source = (
        Path("packages")
        / "adapters"
        / "providers"
        / "lmstudio_responses"
        / "lmstudio_responses_provider.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = [
        "packages.core",
        "packages.provider_runtime",
        "packages.telemetry",
        "apps.",
        "services.",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        # "tool" removed in Phase 2 (docs/TODO/02): the adapter now opt-in
        # supports Responses-API tool-calling. Other dangerous boundaries stay.
        "mcp",
        "memory",
        "intent",
        "voice",
        "desktop",
        "session",
        "history",
        "retry",
        "fallback",
        "routing",
    ]

    assert [token for token in forbidden if token in source] == []
