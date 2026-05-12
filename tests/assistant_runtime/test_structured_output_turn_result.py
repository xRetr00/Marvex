from copy import deepcopy
from pathlib import Path

import pytest

from packages.contracts import ErrorCode, StageStatus, TraceEvent
from packages.telemetry.sanitization import REDACTED


VALID_FINAL_RESPONSE = {
    "schema_version": "0.1.1-draft",
    "response_type": "text",
    "text": "Done.",
    "payload_ref": None,
    "output_channel_intent": "default",
    "safe_for_display": True,
    "safe_for_speech": True,
    "memory_write_candidate_hint": False,
    "finish_reason": "stop",
    "metadata": {"case_name": "accepted"},
}


def handoff(**overrides):
    data = {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-structured-runtime",
        "turn_id": "turn-structured-runtime",
        "state": "valid_structured_result",
        "handoff_status": "usable_structured_payload",
        "target_contract": "AssistantFinalResponse",
        "sanitized_message": "Structured output validated.",
        "sanitized_error_code": None,
        "parsed_payload": deepcopy(VALID_FINAL_RESPONSE),
        "diagnostic_only": False,
    }
    data.update(overrides)
    return data


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def test_valid_handoff_becomes_assistant_turn_result_with_final_response():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    result = consume_structured_output_as_turn_result(handoff())

    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-structured-runtime"
    assert result.turn_id == "turn-structured-runtime"
    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Done."
    assert result.assistant_final_response.schema_version == "0.1.1-draft"
    assert result.assistant_final_response.response_type.value == "text"
    assert result.assistant_final_response.output_channel_intent.value == "default"
    assert result.assistant_final_response.finish_reason.value == "stop"
    assert result.assistant_final_response.safe_for_display is True
    assert result.assistant_final_response.safe_for_speech is True
    assert result.assistant_final_response.metadata == {"case_name": "accepted"}
    assert result.provider_turn_refs == []
    assert result.tool_result_refs == []
    assert result.memory_result_refs == []
    assert result.metadata == {}
    assert [(stage.stage_name, stage.status) for stage in result.stage_summaries] == [
        ("structured_output_consumption", StageStatus.COMPLETED),
        ("final_response_assembly", StageStatus.COMPLETED),
    ]


def test_provider_error_handoff_becomes_deterministic_assistant_error_result():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    result = consume_structured_output_as_turn_result(
        handoff(
            state="provider_error",
            handoff_status="provider_error",
            sanitized_message="Provider could not return structured output.",
            sanitized_error_code="PROVIDER_ERROR",
            parsed_payload=None,
        )
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.PROVIDER_ERROR
    assert result.error.error_id == "turn-structured-runtime:structured-output-consumption"
    assert result.error.message == "Provider could not return structured output."
    assert [(stage.stage_name, stage.status, stage.error_ref) for stage in result.stage_summaries] == [
        (
            "structured_output_consumption",
            StageStatus.FAILED,
            "turn-structured-runtime:structured-output-consumption",
        )
    ]


@pytest.mark.parametrize(
    ("handoff_status", "code"),
    [
        ("invalid_structured_payload", ErrorCode.VALIDATION_ERROR),
        ("provider_timeout", ErrorCode.PROVIDER_TIMEOUT),
        ("refusal_unresolved", ErrorCode.PROVIDER_ERROR),
        ("incomplete_unresolved", ErrorCode.PROVIDER_ERROR),
    ],
)
def test_non_valid_handoff_statuses_map_to_safe_error_results(handoff_status, code):
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    result = consume_structured_output_as_turn_result(
        handoff(
            state=f"{handoff_status}_source",
            handoff_status=handoff_status,
            sanitized_message="Structured output is not usable.",
            sanitized_error_code="STRUCTURED_OUTPUT_NOT_USABLE",
            parsed_payload=None,
        )
    )

    assert result.error is not None
    assert result.error.code == code
    assert result.error.message == "Structured output is not usable."
    assert result.assistant_final_response is None


def test_malformed_or_missing_handoff_data_returns_safe_validation_error():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    result = consume_structured_output_as_turn_result(
        {
            "schema_version": "0.1.1-draft",
            "trace_id": "trace-malformed",
            "turn_id": "turn-malformed",
            "raw_provider_output": "raw provider output",
        }
    )

    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-malformed"
    assert result.turn_id == "turn-malformed"
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Structured output handoff was invalid."
    assert "raw provider output" not in str(result.model_dump()).lower()


def test_non_json_compatible_handoff_data_returns_safe_validation_error():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    result = consume_structured_output_as_turn_result(
        handoff(extra_non_json=object())
    )

    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Structured output handoff was invalid."


def test_invalid_final_response_payload_returns_safe_validation_error():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    result = consume_structured_output_as_turn_result(
        handoff(parsed_payload={**VALID_FINAL_RESPONSE, "text": "   "})
    )

    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Structured output final response was invalid."
    assert result.assistant_final_response is None


def test_handoff_input_is_not_mutated():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    original = handoff()
    before = deepcopy(original)

    consume_structured_output_as_turn_result(original)

    assert original == before


def test_telemetry_emission_uses_existing_sanitized_trace_event_path():
    from packages.assistant_runtime.structured_output_turn_result import (
        consume_structured_output_as_turn_result,
    )

    sink = RecordingTelemetrySink()
    result = consume_structured_output_as_turn_result(
        handoff(raw_provider_output="raw provider output"),
        telemetry_sink=sink,
    )

    assert result.error is not None
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.trace_id == "trace-structured-runtime"
    assert event.event_id == "turn-structured-runtime:final_response_created"
    assert event.data["raw_provider_output"] == REDACTED
    assert "raw provider output" not in str(event.model_dump()).lower()


def test_normal_assistant_runtime_run_remains_unwired_to_structured_output_path():
    from packages.assistant_runtime.runtime import AssistantTurnRuntime

    assert not hasattr(AssistantTurnRuntime, "consume_structured_output_as_turn_result")
    assert "structured_output_turn_result" not in Path(
        "packages/assistant_runtime/runtime.py"
    ).read_text(encoding="utf-8")


def test_package_root_does_not_export_experimental_turn_result_helper():
    import packages.assistant_runtime as package_root

    assert not hasattr(package_root, "consume_structured_output_as_turn_result")


def test_structured_output_turn_result_imports_no_forbidden_boundaries():
    source = Path(
        "packages/assistant_runtime/structured_output_turn_result.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "packages.core",
        "packages.provider_runtime",
        "packages.provider_structured_output",
        "packages.adapters",
        "packages.ports",
        "apps.cli",
        "services",
        "ProviderRequest",
        "ProviderResponse",
        "TurnInput",
        "TurnOutput",
        "json.loads",
        "retry",
        "render_prompt",
    ]

    assert [term for term in forbidden if term in source] == []
