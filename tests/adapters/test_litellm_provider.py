from pathlib import Path
from types import SimpleNamespace

from packages.contracts import (
    ErrorCode,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
)
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
        model="openrouter/test-model",
        input_text="Hello",
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options or {},
    )


def make_responses_response() -> SimpleNamespace:
    return SimpleNamespace(
        id="litellm-response-001",
        status="completed",
        output_text="LiteLLM output",
        output=[],
        usage=SimpleNamespace(input_tokens=3, output_tokens=4, total_tokens=7),
    )


class _FakeResponsesClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.cancel_calls: list[str] = []
        self.delete_calls: list[str] = []

    @property
    def responses(self) -> "_FakeResponsesClient":
        return self

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return make_responses_response()

    def cancel(self, response_id: str) -> SimpleNamespace:
        self.cancel_calls.append(response_id)
        return SimpleNamespace(id=response_id, status="cancelled")

    def delete(self, response_id: str) -> dict[str, object]:
        self.delete_calls.append(response_id)
        return {"id": response_id, "object": "response", "deleted": True}


def test_adapter_satisfies_provider_port():
    from packages.adapters.providers.litellm import LiteLLMProvider

    assert isinstance(LiteLLMProvider(), ProviderPort)


def test_litellm_called_with_responses_input_and_instructions(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    response = LiteLLMProvider().send(make_request())

    assert response.output_text == "LiteLLM output"
    assert calls == [
        {
            "model": "openrouter/test-model",
            "input": "Hello",
            "instructions": "Follow system guidance.",
            "previous_response_id": "prev-001",
        }
    ]


def test_litellm_config_base_url_and_timeout_are_forwarded(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider(
        LiteLLMProviderConfig(
            base_url="http://127.0.0.1:4000",
            timeout_seconds=5,
        )
    ).send(make_request())

    assert calls[0]["api_base"] == "http://127.0.0.1:4000"
    assert calls[0]["timeout"] == 5


def test_litellm_proxy_mode_uses_openai_responses_client_and_preserves_model(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    sdk_calls: list[dict[str, object]] = []
    client_kwargs: list[dict[str, object]] = []
    client = _FakeResponsesClient()

    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kwargs: sdk_calls.append(kwargs),
    )

    def fake_client_factory(**kwargs: object) -> _FakeResponsesClient:
        client_kwargs.append(kwargs)
        return client

    response = LiteLLMProvider(
        LiteLLMProviderConfig(
            base_url="http://127.0.0.1:4000/v1",
            api_key="litellm-key",
            provider_mode="litellm_proxy",
            timeout_seconds=5,
        ),
        client_factory=fake_client_factory,
    ).send(make_request().model_copy(update={"model": "chatgpt-web/gpt-5.5-thinking"}))

    assert response.output_text == "LiteLLM output"
    assert sdk_calls == []
    assert client_kwargs == [
        {
            "base_url": "http://127.0.0.1:4000/v1",
            "api_key": "litellm-key",
            "timeout": 5,
        }
    ]
    assert client.calls[0]["model"] == "chatgpt-web/gpt-5.5-thinking"
    assert client.calls[0]["input"] == "Hello"
    assert client.calls[0]["instructions"] == "Follow system guidance."
    assert client.calls[0]["previous_response_id"] == "prev-001"
    assert "api_base" not in client.calls[0]
    assert "messages" not in client.calls[0]


def test_litellm_proxy_response_cancel_and_delete_use_openai_responses_client():
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig

    client = _FakeResponsesClient()

    def fake_client_factory(**kwargs: object) -> _FakeResponsesClient:
        return client

    provider = LiteLLMProvider(
        LiteLLMProviderConfig(
            base_url="http://127.0.0.1:4000/v1",
            api_key="litellm-key",
            provider_mode="litellm_proxy",
        ),
        client_factory=fake_client_factory,
    )

    cancelled = provider.cancel_response("resp-cancel")
    deleted = provider.delete_response("resp-delete")

    assert client.cancel_calls == ["resp-cancel"]
    assert client.delete_calls == ["resp-delete"]
    assert cancelled["id"] == "resp-cancel"
    assert cancelled["status"] == "cancelled"
    assert deleted == {"id": "resp-delete", "object": "response", "deleted": True}


def test_litellm_proxy_stream_uses_responses_streaming_client():
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig

    class StreamClient(_FakeResponsesClient):
        def create(self, **kwargs: object) -> list[SimpleNamespace]:
            self.calls.append(kwargs)
            return [
                SimpleNamespace(
                    type="response.reasoning_text.done",
                    item_id="rs-stream",
                    output_index=0,
                    content_index=0,
                    text="Thinking.",
                ),
                SimpleNamespace(type="response.output_text.delta", delta="Hi"),
                SimpleNamespace(
                    type="response.completed",
                    response=SimpleNamespace(
                        id="resp-stream",
                        output_text="Hi",
                        output=[],
                        status="completed",
                    ),
                ),
            ]

    client = StreamClient()

    def fake_client_factory(**kwargs: object) -> StreamClient:
        return client

    events = list(
        LiteLLMProvider(
            LiteLLMProviderConfig(
                base_url="http://127.0.0.1:4000/v1",
                provider_mode="litellm_proxy",
            ),
            client_factory=fake_client_factory,
        ).stream_send(make_request())
    )

    assert client.calls[0]["stream"] is True
    assert client.calls[0]["previous_response_id"] == "prev-001"
    assert events[-1].response_id == "resp-stream"
    assert events[-1].output_text == "<think>Thinking.</think>Hi"


def test_litellm_openai_compatible_mode_prefixes_plain_model_ids(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider(
        LiteLLMProviderConfig(
            base_url="http://localhost:20128/v1",
            provider_mode="openai_compatible",
        )
    ).send(make_request().model_copy(update={"model": "omniroute-qwen"}))

    assert calls[0]["model"] == "openai/omniroute-qwen"
    assert calls[0]["api_base"] == "http://localhost:20128/v1"


def test_litellm_openai_compatible_mode_preserves_prefixed_model_ids(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider(
        LiteLLMProviderConfig(
            base_url="http://localhost:20128/v1",
            provider_mode="openai_compatible",
        )
    ).send(make_request().model_copy(update={"model": "openai/gpt-4o-mini"}))

    assert calls[0]["model"] == "openai/gpt-4o-mini"


def test_litellm_openrouter_mode_prefixes_providerless_openrouter_model_ids(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider(
        LiteLLMProviderConfig(
            api_key="sk-or-test",
            provider_mode="litellm_openrouter",
        )
    ).send(make_request().model_copy(update={"model": "deepseek/deepseek-v4-flash"}))

    assert calls[0]["model"] == "openrouter/deepseek/deepseek-v4-flash"
    assert calls[0]["api_key"] == "sk-or-test"
    assert "api_base" not in calls[0]
    assert "messages" not in calls[0]


def test_litellm_openrouter_mode_preserves_already_prefixed_model_ids(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider(
        LiteLLMProviderConfig(provider_mode="litellm_openrouter")
    ).send(make_request().model_copy(update={"model": "openrouter/openai/gpt-oss-20b:free"}))

    assert calls[0]["model"] == "openrouter/openai/gpt-oss-20b:free"


def test_litellm_request_timeout_overrides_config_timeout(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider, LiteLLMProviderConfig
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider(LiteLLMProviderConfig(timeout_seconds=5)).send(
        make_request(provider_options={"timeout": 12})
    )

    assert calls[0]["timeout"] == 12


def test_input_text_without_instructions_omits_instruction_arg(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider().send(make_request(instructions=None))

    assert calls[0]["input"] == "Hello"
    assert "instructions" not in calls[0]


def test_previous_response_id_is_sent_to_responses_api_and_metadata(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    response = LiteLLMProvider().send(
        make_request(previous_response_id="previous-response")
    )

    assert calls[0]["previous_response_id"] == "previous-response"
    assert response.raw_metadata["previous_response_id"] == "previous-response"
    assert response.raw_metadata["api_surface"] == "responses"


def test_output_response_id_finish_reason_and_usage_are_parsed(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kwargs: make_responses_response(),
    )

    response = LiteLLMProvider().send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.provider_name == "litellm"
    assert validated.response_id == "litellm-response-001"
    assert validated.output_text == "LiteLLM output"
    assert validated.finish_reason == FinishReason.STOP
    assert validated.usage == {
        "input_tokens": 3,
        "output_tokens": 4,
        "total_tokens": 7,
    }


def test_exception_maps_to_error_envelope(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    def fake_responses(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    response = LiteLLMProvider().send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.output_text == ""
    assert validated.finish_reason == FinishReason.ERROR
    assert validated.error is not None
    assert validated.error.code == ErrorCode.PROVIDER_ERROR
    assert validated.error.message == "provider unavailable"
    assert validated.error.source == "litellm_provider"


def test_provider_options_allowlist_filters_and_records_ignored(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    response = LiteLLMProvider().send(
        make_request(
            provider_options={
                "temperature": 0.2,
                "max_tokens": 100,
                "max_output_tokens": 120,
                "timeout": 30,
                "parallel_tool_calls": False,
                "api_key": "secret",
                "tools": [{"name": "forbidden"}],
                "unknown": True,
            }
        )
    )

    assert calls[0]["temperature"] == 0.2
    assert calls[0]["max_output_tokens"] == 120
    assert calls[0]["timeout"] == 30
    assert calls[0]["parallel_tool_calls"] is False
    assert "max_tokens" not in calls[0]
    assert "api_key" not in calls[0]
    assert "tools" not in calls[0]
    assert "unknown" not in calls[0]
    assert response.raw_metadata["ignored_provider_options"] == [
        "api_key",
        "tools",
        "unknown",
    ]


def test_reasoning_options_are_sent_as_non_null_responses_reasoning(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider().send(
        make_request(
            provider_options={
                "reasoning_effort": "high",
                "reasoning_summary": "auto",
            }
        )
    )

    assert calls[0]["reasoning"] == {"effort": "high", "summary": "auto"}


def test_reasoning_effort_aliases_are_normalized_before_responses_request(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider().send(make_request(provider_options={"reasoning_effort": "on"}))

    assert calls[0]["reasoning"] == {"effort": "medium"}


def test_no_tools_mcp_or_streaming_fields_sent(monkeypatch):
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return make_responses_response()

    monkeypatch.setattr(litellm_provider.litellm, "responses", fake_responses)

    LiteLLMProvider().send(make_request())

    forbidden = {"tools", "mcp", "stream", "streaming", "messages"}
    assert forbidden.isdisjoint(calls[0])


def test_adapter_source_has_no_forbidden_boundary_imports_or_raw_http():
    source = (
        Path("packages")
        / "adapters"
        / "providers"
        / "litellm"
        / "litellm_provider.py"
    ).read_text(encoding="utf-8").lower()
    # "tool" was removed from this list in Phase 2 (docs/TODO/02): the adapter
    # now opt-in supports OpenAI-style tool-calling (sends request.tools, parses
    # response tool_calls). "stream" was removed in item 06: the adapter now has
    # an opt-in stream_send that yields packages.contracts streaming events (the
    # non-streaming send stays unchanged, asserted separately). The genuinely
    # dangerous boundaries below remain forbidden - no raw HTTP, no
    # cross-boundary package imports, no mcp/lmstudio/voice/etc. coupling.
    forbidden = [
        "ht" + "tpx",
        "req" + "uests",
        "url" + "lib",
        "soc" + "ket",
        "sub" + "process",
        "packages.core",
        "packages.ports",
        "packages.telemetry",
        "apps.",
        "services.",
        "lmstudio",
        "mcp",
        "memory",
        "intent",
        "voice",
        "desktop",
        "session",
        "history",
    ]

    assert [token for token in forbidden if token in source] == []
