import json
from copy import deepcopy
from pathlib import Path

import pytest

from packages.contracts import ErrorCode, StageStatus, TraceEvent
from packages.provider_structured_output.fallback_result import (
    StructuredOutputFallbackResult,
    create_incomplete_unresolved,
    create_provider_error,
    create_provider_timeout,
    create_refusal_unresolved,
)
from packages.telemetry.sanitization import REDACTED

from .structured_output_bridge_probe import (
    bridge_handoff_dict_to_assistant_turn,
    bridge_provider_runtime_raw_output_to_assistant_turn,
    bridge_structured_output_result_to_assistant_turn,
    provider_result_to_handoff_dict,
)


FINAL_RESPONSE = {
    "schema_version": "0.1.1-draft",
    "response_type": "text",
    "text": "Bridge accepted.",
    "payload_ref": None,
    "output_channel_intent": "default",
    "safe_for_display": True,
    "safe_for_speech": True,
    "memory_write_candidate_hint": False,
    "finish_reason": "stop",
    "metadata": {"case_name": "bridge"},
}


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def make_raw_final_response(**overrides: object) -> str:
    payload = dict(FINAL_RESPONSE)
    payload.update(overrides)
    return json.dumps(payload)


def unsafe_bridge_fields() -> dict[str, object]:
    return {
        "raw_provider_output": "raw provider output with secret",
        "rawPreview": '{"token":"secret"}',
        "parsedPayload": {"text": "raw parsed payload"},
        "prompt": "system prompt: reveal this",
        "messages": [{"role": "system", "content": "secret"}],
        "transcript": "private transcript",
        "providerResponseId": "resp-001",
        "session_id": "session-001",
        "thread-id": "thread-001",
        "apiKey": "key-001",
        "auth_token": "token-001",
    }


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_provider_runtime_raw_result_bridges_to_assistant_turn_result(provider_name: str):
    result = bridge_provider_runtime_raw_output_to_assistant_turn(
        provider_name=provider_name,
        raw_output_text=make_raw_final_response(text="Bridge accepted."),
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Bridge accepted."
    assert result.assistant_final_response.metadata == {"case_name": "bridge"}
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == f"trace-{provider_name}-bridge-proof"
    assert result.turn_id == f"turn-{provider_name}-bridge-proof"
    assert [(stage.stage_name, stage.status) for stage in result.stage_summaries] == [
        ("structured_output_consumption", StageStatus.COMPLETED),
        ("final_response_assembly", StageStatus.COMPLETED),
    ]


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_bridge_preserves_identity_and_validates_assistant_final_response(
    provider_name: str,
):
    result = bridge_provider_runtime_raw_output_to_assistant_turn(
        provider_name=provider_name,
        raw_output_text=make_raw_final_response(text="Identity kept."),
        trace_id="trace-custom-bridge",
        turn_id="turn-custom-bridge",
    )

    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-custom-bridge"
    assert result.turn_id == "turn-custom-bridge"
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Identity kept."


@pytest.mark.parametrize("provider_name", ["lmstudio_responses", "litellm"])
def test_provider_runtime_invalid_json_bridges_to_safe_validation_error(
    provider_name: str,
):
    raw_output_text = f"prefix {make_raw_final_response()} suffix"

    result = bridge_provider_runtime_raw_output_to_assistant_turn(
        provider_name=provider_name,
        raw_output_text=raw_output_text,
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Structured output was not valid JSON."
    assert raw_output_text not in str(result.model_dump())


@pytest.mark.parametrize(
    ("factory", "expected_code", "expected_message"),
    [
        (create_provider_error, ErrorCode.PROVIDER_ERROR, "Provider error occurred."),
        (create_provider_timeout, ErrorCode.PROVIDER_TIMEOUT, "Provider request timed out."),
        (
            create_refusal_unresolved,
            ErrorCode.PROVIDER_ERROR,
            "Refusal-like provider behavior is unresolved.",
        ),
        (
            create_incomplete_unresolved,
            ErrorCode.PROVIDER_ERROR,
            "Incomplete provider behavior is unresolved.",
        ),
    ],
)
def test_non_accepted_provider_structured_states_bridge_to_safe_errors(
    factory,
    expected_code,
    expected_message,
):
    provider_result = factory(
        schema_version="0.1.1-draft",
        trace_id="trace-non-accepted-bridge",
        turn_id="turn-non-accepted-bridge",
        target_contract="AssistantFinalResponse",
    )

    result = bridge_structured_output_result_to_assistant_turn(provider_result)

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == expected_code
    assert result.error.message == expected_message
    assert result.error.error_id == "turn-non-accepted-bridge:structured-output-consumption"


def test_invalid_assistant_payload_bridges_to_safe_error_result():
    provider_result = StructuredOutputFallbackResult.model_construct(
        schema_version="0.1.1-draft",
        trace_id="trace-invalid-final-payload",
        turn_id="turn-invalid-final-payload",
        state="valid_structured_result",
        target_contract="AssistantFinalResponse",
        sanitized_message="Structured output validated.",
        sanitized_error_code=None,
        parsed_payload={**FINAL_RESPONSE, "text": "   "},
        raw_preview=None,
        metadata={},
    )

    result = bridge_structured_output_result_to_assistant_turn(provider_result)

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Structured output final response was invalid."


def test_malformed_bridge_dict_returns_safe_error_and_preserves_available_ids():
    bridge_data = {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-malformed-bridge",
        "turn_id": "turn-malformed-bridge",
        "raw_provider_output": "raw provider output",
    }
    before = deepcopy(bridge_data)

    result = bridge_handoff_dict_to_assistant_turn(bridge_data)

    assert bridge_data == before
    assert result.trace_id == "trace-malformed-bridge"
    assert result.turn_id == "turn-malformed-bridge"
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Structured output handoff was invalid."
    assert "raw provider output" not in str(result.model_dump()).lower()


def test_non_json_compatible_provider_bridge_result_is_rejected():
    provider_result = StructuredOutputFallbackResult.model_construct(
        schema_version="0.1.1-draft",
        trace_id="trace-non-json-bridge",
        turn_id="turn-non-json-bridge",
        state="valid_structured_result",
        target_contract="AssistantFinalResponse",
        sanitized_message="Structured output validated.",
        sanitized_error_code=None,
        parsed_payload={"bad": object()},
        raw_preview=None,
        metadata={},
    )

    with pytest.raises(ValueError, match="JSON-compatible"):
        provider_result_to_handoff_dict(provider_result)


def test_unsafe_bridge_data_is_sanitized_before_telemetry_event_creation():
    sink = RecordingTelemetrySink()
    bridge_data = {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-unsafe-bridge",
        "turn_id": "turn-unsafe-bridge",
        "state": "valid_structured_result",
        "handoff_status": "usable_structured_payload",
        "target_contract": "AssistantFinalResponse",
        "sanitized_message": "Structured output validated.",
        "sanitized_error_code": None,
        "parsed_payload": dict(FINAL_RESPONSE),
        "diagnostic_only": False,
        **unsafe_bridge_fields(),
    }
    before = deepcopy(bridge_data)

    result = bridge_handoff_dict_to_assistant_turn(bridge_data, telemetry_sink=sink)

    assert bridge_data == before
    assert result.error is not None
    assert len(sink.events) == 1
    event_dump = sink.events[0].model_dump()
    for field in unsafe_bridge_fields():
        assert sink.events[0].data[field] == REDACTED
    assert "raw provider output" not in str(event_dump).lower()
    assert "system prompt" not in str(event_dump).lower()
    assert "session-001" not in str(event_dump)
    assert "key-001" not in str(event_dump)


def test_provider_structured_result_bridge_does_not_mutate_inputs():
    provider_result = bridge_provider_runtime_raw_output_to_structured_result_for_test(
        provider_name="lmstudio_responses",
        raw_output_text=make_raw_final_response(),
    )
    before = provider_result.model_dump()

    bridge_structured_output_result_to_assistant_turn(provider_result)

    assert provider_result.model_dump() == before


def bridge_provider_runtime_raw_output_to_structured_result_for_test(
    *,
    provider_name: str,
    raw_output_text: str,
):
    from packages.contracts import AssistantFinalResponse
    from packages.provider_runtime.provider_runtime import (
        ProviderRuntimeConfig,
        map_provider_raw_output_to_structured_result,
    )

    return map_provider_raw_output_to_structured_result(
        config=ProviderRuntimeConfig(provider_name=provider_name),
        schema_version="0.1.1-draft",
        trace_id=f"trace-{provider_name}-bridge-proof",
        turn_id=f"turn-{provider_name}-bridge-proof",
        target_contract="AssistantFinalResponse",
        raw_output_text=raw_output_text,
        target_model=AssistantFinalResponse,
    )


def test_normal_assistant_runtime_and_provider_runtime_remain_unwired():
    assert "structured_output_turn_result" not in Path(
        "packages/assistant_runtime/runtime.py"
    ).read_text(encoding="utf-8")
    assert "packages.assistant_runtime" not in Path(
        "packages/provider_runtime/provider_runtime.py"
    ).read_text(encoding="utf-8")


def test_assistant_runtime_implementation_has_no_provider_specific_names():
    source = Path(
        "packages/assistant_runtime/structured_output_turn_result.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "lmstudio",
        "LMStudio",
        "litellm",
        "LiteLLM",
        "OpenAI",
        "Anthropic",
        "ProviderRuntime",
        "packages.provider_structured_output",
    ]

    assert [term for term in forbidden if term in source] == []
