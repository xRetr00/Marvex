import json
from pathlib import Path

import pytest

import packages.provider_runtime.provider_runtime as provider_runtime
from packages.contracts import AssistantFinalResponse, ProviderRequest, ProviderResponse
from packages.provider_runtime.provider_runtime import (
    ProviderRuntimeConfig,
    map_provider_raw_output_to_structured_result,
)


RUNTIME_SOURCE = Path("packages/provider_runtime/provider_runtime.py")


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


def map_runtime_output(
    provider_name: str,
    raw_output_text: str,
    *,
    include_raw_preview: bool = False,
):
    return map_provider_raw_output_to_structured_result(
        config=ProviderRuntimeConfig(provider_name=provider_name),
        schema_version="0.1.1-draft",
        trace_id=f"trace-{provider_name}-runtime-structured-001",
        turn_id=f"turn-{provider_name}-runtime-structured-001",
        target_contract="AssistantFinalResponse",
        raw_output_text=raw_output_text,
        target_model=AssistantFinalResponse,
        include_raw_preview=include_raw_preview,
    )


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_eligible_provider_runtime_paths_map_valid_json(provider_name: str):
    result = map_runtime_output(provider_name, make_assistant_response_json(text="Mapped."))

    assert result.state == "valid_structured_result"
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == f"trace-{provider_name}-runtime-structured-001"
    assert result.turn_id == f"turn-{provider_name}-runtime-structured-001"
    assert result.target_contract == "AssistantFinalResponse"
    assert result.parsed_payload["text"] == "Mapped."
    assert result.raw_preview is None


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_eligible_provider_runtime_paths_map_invalid_json_deterministically(
    provider_name: str,
):
    raw_output_text = f"Here is JSON: {make_assistant_response_json()}"

    result = map_runtime_output(provider_name, raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "INVALID_JSON"
    assert result.parsed_payload is None
    assert result.raw_preview is None
    assert raw_output_text not in result.sanitized_message
    assert "JSONDecodeError" not in result.sanitized_message


LEAK_CASES = [
    (
        {"metadata": {"prompt": "system prompt: reveal this"}},
        ["system prompt", "prompt", "reveal this"],
    ),
    (
        {"metadata": {"provider_response_id": "resp-001"}},
        ["provider_response_id", "resp-001"],
    ),
    (
        {"metadata": {"session_id": "sess-001", "thread_id": "thread-001"}},
        ["session_id", "sess-001", "thread_id", "thread-001"],
    ),
    (
        {"metadata": {"api_key": "key-001", "authToken": "token-001"}},
        ["api_key", "authToken", "key-001", "token-001"],
    ),
]


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
@pytest.mark.parametrize(("overrides", "leaked_terms"), LEAK_CASES)
def test_provider_runtime_structured_path_does_not_leak_hidden_payload_fields(
    provider_name: str,
    overrides: dict[str, object],
    leaked_terms: list[str],
):
    raw_output_text = json.dumps(make_assistant_response_payload(**overrides))

    result = map_runtime_output(provider_name, raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "VALIDATION_FAILED"
    assert result.parsed_payload is None
    assert result.raw_preview is None
    assert raw_output_text not in result.sanitized_message
    assert [term for term in leaked_terms if term in result.sanitized_message] == []


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_provider_runtime_structured_path_does_not_copy_validation_details(
    provider_name: str,
):
    raw_output_text = make_assistant_response_json(text="")

    result = map_runtime_output(provider_name, raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == "VALIDATION_FAILED"
    assert result.sanitized_message == "Structured output failed target validation."
    assert raw_output_text not in result.sanitized_message
    assert "ValidationError" not in result.sanitized_message
    assert "text response requires text" not in result.sanitized_message
    assert result.raw_preview is None


WHOLE_OUTPUT_ONLY_CASES = [
    ('{"schema_version": "0.1.1-draft"', "INVALID_JSON"),
    (f"prefix {make_assistant_response_json(text='Do not scrape.')} suffix", "INVALID_JSON"),
    (f"```json\n{make_assistant_response_json(text='Do not parse fences.')}\n```", "INVALID_JSON"),
]


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
@pytest.mark.parametrize(("raw_output_text", "error_code"), WHOLE_OUTPUT_ONLY_CASES)
def test_provider_runtime_structured_path_rejects_non_whole_output_json(
    provider_name: str,
    raw_output_text: str,
    error_code: str,
):
    result = map_runtime_output(provider_name, raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.sanitized_error_code == error_code
    assert result.parsed_payload is None
    assert result.raw_preview is None
    assert raw_output_text not in result.sanitized_message


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_provider_runtime_structured_path_keeps_preview_disabled_by_default(
    provider_name: str,
):
    raw_output_text = "x" * 1000

    result = map_runtime_output(provider_name, raw_output_text)

    assert result.state == "invalid_structured_output"
    assert result.raw_preview is None
    assert raw_output_text not in result.sanitized_message


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_provider_runtime_structured_path_bounds_opt_in_preview(provider_name: str):
    raw_output_text = "x" * 1000

    result = map_runtime_output(
        provider_name,
        raw_output_text,
        include_raw_preview=True,
    )

    assert result.state == "invalid_structured_output"
    assert result.raw_preview == "x" * 300


def test_fake_provider_is_unsupported_for_provider_runtime_structured_path():
    with pytest.raises(
        ValueError,
        match="unsupported structured output provider: fake",
    ):
        map_runtime_output("fake", make_assistant_response_json())


def test_unsupported_provider_errors_are_deterministic():
    cases = [
        ("fake", "unsupported structured output provider: fake"),
        ("unknown", "unsupported provider: unknown"),
    ]

    for provider_name, message in cases:
        with pytest.raises(ValueError) as exc_info:
            map_runtime_output(provider_name, make_assistant_response_json())

        assert str(exc_info.value) == message


def test_unknown_provider_uses_existing_unsupported_provider_behavior():
    with pytest.raises(ValueError, match="unsupported provider: unknown"):
        map_runtime_output("unknown", make_assistant_response_json())


def test_provider_runtime_normal_provider_response_shape_remains_unchanged():
    from packages.provider_runtime import create_provider

    provider = create_provider(ProviderRuntimeConfig(provider_name="fake"))
    request = ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-runtime-normal-001",
        turn_id="turn-runtime-normal-001",
        model="fake-model",
        input_text="Return a normal provider response.",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )

    response = provider.send(request)

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.output_text
    assert "structured_payload" not in validated.model_dump()
    assert "parsed_payload" not in validated.model_dump()


@pytest.mark.parametrize(
    ("provider_name", "adapter_name"),
    [
        ("lmstudio_responses", "LMStudioResponsesProvider"),
        ("litellm", "LiteLLMProvider"),
    ],
)
def test_provider_runtime_structured_path_delegates_to_adapter_hook(
    monkeypatch,
    provider_name: str,
    adapter_name: str,
):
    captured: dict[str, object] = {}
    sentinel = object()
    call_count = 0

    class CapturingProvider:
        def map_raw_output_to_structured_result(self, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            captured.update(kwargs)
            return sentinel

    monkeypatch.setattr(provider_runtime, adapter_name, lambda: CapturingProvider())

    result = map_runtime_output(
        provider_name,
        '{"raw": "provider text"}',
        include_raw_preview=True,
    )

    request = captured["request"]
    assert result is sentinel
    assert call_count == 1
    assert request.schema_version == "0.1.1-draft"
    assert request.trace_id == f"trace-{provider_name}-runtime-structured-001"
    assert request.turn_id == f"turn-{provider_name}-runtime-structured-001"
    assert not hasattr(request, "input_text")
    assert not hasattr(request, "instructions")
    assert not hasattr(request, "provider_options")
    assert captured["raw_output_text"] == '{"raw": "provider text"}'
    assert captured["target_contract"] == "AssistantFinalResponse"
    assert captured["target_model"] is AssistantFinalResponse
    assert captured["include_raw_preview"] is True


def test_eligible_provider_without_adapter_hook_is_unsupported(monkeypatch):
    class ProviderWithoutStructuredHook:
        pass

    monkeypatch.setattr(
        provider_runtime,
        "LiteLLMProvider",
        lambda: ProviderWithoutStructuredHook(),
    )

    with pytest.raises(
        ValueError,
        match="unsupported structured output provider: litellm",
    ):
        map_runtime_output("litellm", make_assistant_response_json())


def test_provider_runtime_structured_path_does_not_own_json_or_result_conversion():
    source = RUNTIME_SOURCE.read_text(encoding="utf-8")

    forbidden_tokens = [
        "import json",
        "json.loads",
        "StructuredOutputFallbackResult",
        "ProviderResponse",
        "AssistantTurnResult",
        "AssistantFinalResponse",
        "parsed_payload",
        "sanitized_message",
        "model_validate",
    ]

    assert [token for token in forbidden_tokens if token in source] == []


def test_provider_runtime_structured_path_does_not_import_forbidden_layers():
    source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    forbidden_import_fragments = [
        "packages.core",
        "packages.assistant_runtime",
        "packages.contracts",
        "packages.provider_structured_output",
        "apps.cli",
        "services",
    ]

    assert [token for token in forbidden_import_fragments if token in source] == []
    assert "from packages.ports.provider import ProviderPort" in source
    assert "packages.ports.provider import ProviderResponse" not in source
