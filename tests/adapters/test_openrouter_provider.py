from types import SimpleNamespace

from packages.contracts import FinishReason, ProviderRequest, ProviderResponse
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
        model="openai/gpt-oss-20b:free",
        input_text="Hello",
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options or {},
    )


class RecordingResponses:
    def __init__(self, response: object | None = None, exception: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._response = response or SimpleNamespace(
            id="resp-openrouter",
            output_text="OpenRouter output",
            status="completed",
            usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
            openrouter_metadata={"provider_name": "OpenInference"},
        )
        self._exception = exception

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._response


class RecordingBeta:
    def __init__(self, responses: RecordingResponses) -> None:
        self.responses = responses


class RecordingClient:
    def __init__(self, responses: RecordingResponses) -> None:
        self.beta = RecordingBeta(responses)


class RecordingClientFactory:
    def __init__(self, client: RecordingClient) -> None:
        self.client = client
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.client


def test_adapter_satisfies_provider_port():
    from packages.adapters.providers.openrouter import OpenRouterProvider

    assert isinstance(OpenRouterProvider(client_factory=RecordingClientFactory(RecordingClient(RecordingResponses()))), ProviderPort)


def test_sdk_client_created_with_openrouter_key_and_metadata_headers():
    from packages.adapters.providers.openrouter import OpenRouterProvider, OpenRouterProviderConfig

    responses = RecordingResponses()
    factory = RecordingClientFactory(RecordingClient(responses))

    OpenRouterProvider(
        OpenRouterProviderConfig(api_key="sk-or-test"),
        client_factory=factory,
    ).send(make_request())

    assert factory.calls == [
        {
            "api_key": "sk-or-test",
            "http_referer": "https://marvex.local",
            "x_title": "Marvex",
        }
    ]


def test_responses_send_receives_responses_api_arguments_without_completion_fields():
    from packages.adapters.providers.openrouter import OpenRouterProvider, OpenRouterProviderConfig

    responses = RecordingResponses()
    provider = OpenRouterProvider(
        OpenRouterProviderConfig(api_key="sk-or-test"),
        client_factory=RecordingClientFactory(RecordingClient(responses)),
    )

    provider.send(
        make_request(
            provider_options={
                "temperature": 0.2,
                "max_output_tokens": 8,
                "messages": [{"role": "user", "content": "bad"}],
                "stream": True,
            }
        )
    )

    assert responses.calls == [
        {
            "model": "openai/gpt-oss-20b:free",
            "input": "Hello",
            "instructions": "Follow system guidance.",
            "previous_response_id": "prev-001",
            "temperature": 0.2,
            "max_output_tokens": 8,
            "http_headers": {"X-OpenRouter-Metadata": "enabled"},
            "stream": False,
        }
    ]


def test_response_id_output_text_usage_and_openrouter_metadata_are_parsed():
    from packages.adapters.providers.openrouter import OpenRouterProvider, OpenRouterProviderConfig

    responses = RecordingResponses()
    provider = OpenRouterProvider(
        OpenRouterProviderConfig(api_key="sk-or-test"),
        client_factory=RecordingClientFactory(RecordingClient(responses)),
    )

    response = provider.send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.provider_name == "openrouter"
    assert validated.response_id == "resp-openrouter"
    assert validated.output_text == "OpenRouter output"
    assert validated.finish_reason == FinishReason.STOP
    assert validated.usage == {
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
    }
    assert validated.raw_metadata["api_surface"] == "responses"
    assert validated.raw_metadata["openrouter_metadata"] == {"provider_name": "OpenInference"}


def test_sdk_exception_maps_to_redacted_error_envelope():
    from packages.adapters.providers.openrouter import OpenRouterProvider, OpenRouterProviderConfig

    responses = RecordingResponses(exception=RuntimeError("bad key sk-or-test"))
    provider = OpenRouterProvider(
        OpenRouterProviderConfig(api_key="sk-or-test"),
        client_factory=RecordingClientFactory(RecordingClient(responses)),
    )

    response = provider.send(make_request())

    assert response.finish_reason == FinishReason.ERROR
    assert response.error is not None
    assert response.error.source == "openrouter_provider"
    assert "sk-or-test" not in response.error.message
    assert "[REDACTED]" in response.error.message
