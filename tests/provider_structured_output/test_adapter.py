from dataclasses import dataclass

from packages.contracts import AssistantFinalResponse, ErrorCode, ErrorEnvelope
from packages.provider_structured_output import (
    validate_fake_adapter_structured_result,
    validate_structured_payload,
    validate_structured_result,
)


def _valid_response_payload(**overrides: object) -> dict[str, object]:
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


STRUCTURED_RESULT_HANDOFF_EXAMPLE = {
    "trace_id": "trace-handoff-001",
    "structured_payload": _valid_response_payload(text="Handoff example."),
}


@dataclass
class FakeStructuredPayload:
    schema_version: str
    response_type: str
    text: str
    payload_ref: object
    output_channel_intent: str
    safe_for_display: bool
    safe_for_speech: bool
    memory_write_candidate_hint: bool
    finish_reason: str
    metadata: dict[str, object]


@dataclass
class FakeStructuredResult:
    trace_id: str
    structured_payload: object | None


@dataclass
class FakeAdapterResult:
    trace_id: str
    result: object | None = None
    error: object | None = None


@dataclass
class FakeAdapterPayloadResult:
    structured_payload: object | None


def test_valid_fake_structured_payload_validates_into_target_contract():
    result = validate_structured_payload(
        _valid_response_payload(),
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Done."
    assert result.metadata == {}


def test_valid_fake_structured_object_validates_into_target_contract():
    payload = FakeStructuredPayload(**_valid_response_payload(text="Object payload."))

    result = validate_structured_payload(payload, AssistantFinalResponse)

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Object payload."


def test_invalid_fake_structured_payload_returns_error_envelope():
    result = validate_structured_payload(
        _valid_response_payload(text="", trace_id="trace-structured-001"),
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-structured-001"
    assert result.code == ErrorCode.VALIDATION_ERROR
    assert result.source == "provider_structured_output"
    assert result.details["target"] == "AssistantFinalResponse"
    assert result.details["errors"]


def test_invalid_payload_uses_explicit_trace_id_when_payload_has_none():
    result = validate_structured_payload(
        _valid_response_payload(text=""),
        AssistantFinalResponse,
        trace_id="trace-explicit-001",
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-explicit-001"


def test_adapter_does_not_create_provider_refs_or_response_ids():
    result = validate_structured_payload(
        _valid_response_payload(),
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    dumped = result.model_dump()
    assert "provider_turn_refs" not in dumped
    response_id_key = "provider" + "_response_id"
    assert response_id_key not in dumped


def test_fake_result_with_structured_payload_validates_into_target_contract():
    result = validate_structured_result(
        {
            "trace_id": "trace-result-001",
            "structured_payload": _valid_response_payload(text="Mapped."),
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Mapped."


def test_fake_result_object_with_structured_payload_validates_into_target_contract():
    fake_result = FakeStructuredResult(
        trace_id="trace-result-002",
        structured_payload=_valid_response_payload(text="Mapped object."),
    )

    result = validate_structured_result(fake_result, AssistantFinalResponse)

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Mapped object."


def test_fake_result_missing_structured_payload_returns_error_envelope():
    result = validate_structured_result(
        {"trace_id": "trace-result-missing-001"},
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-result-missing-001"
    assert result.code == ErrorCode.VALIDATION_ERROR
    assert result.source == "provider_structured_output"
    assert result.details == {
        "target": "AssistantFinalResponse",
        "field": "structured_payload",
    }


def test_fake_result_invalid_structured_payload_returns_error_envelope():
    result = validate_structured_result(
        {
            "trace_id": "trace-result-invalid-001",
            "structured_payload": _valid_response_payload(text=""),
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-result-invalid-001"
    assert result.details["target"] == "AssistantFinalResponse"
    assert result.details["errors"]


def test_result_mapping_uses_explicit_trace_id_first():
    result = validate_structured_result(
        {
            "trace_id": "trace-result-ignored-001",
            "structured_payload": _valid_response_payload(text=""),
        },
        AssistantFinalResponse,
        trace_id="trace-explicit-result-001",
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-explicit-result-001"


def test_result_mapping_does_not_create_provider_refs_or_response_ids():
    result = validate_structured_result(
        {
            "trace_id": "trace-result-003",
            "structured_payload": _valid_response_payload(),
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    dumped = result.model_dump()
    assert "provider_turn_refs" not in dumped
    response_id_key = "provider" + "_response_id"
    assert response_id_key not in dumped


def test_handoff_example_shape_validates_into_target_contract():
    result = validate_structured_result(
        STRUCTURED_RESULT_HANDOFF_EXAMPLE,
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Handoff example."


def test_handoff_example_requires_structured_payload():
    missing_payload_example = {"trace_id": "trace-handoff-missing-001"}

    result = validate_structured_result(
        missing_payload_example,
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-handoff-missing-001"
    assert result.details == {
        "target": "AssistantFinalResponse",
        "field": "structured_payload",
    }


def test_handoff_example_does_not_require_or_create_response_metadata():
    result = validate_structured_result(
        STRUCTURED_RESULT_HANDOFF_EXAMPLE,
        AssistantFinalResponse,
    )

    assert "result_metadata" not in STRUCTURED_RESULT_HANDOFF_EXAMPLE
    assert isinstance(result, AssistantFinalResponse)
    dumped = result.model_dump()
    assert "provider_turn_refs" not in dumped
    response_id_key = "provider" + "_response_id"
    assert response_id_key not in dumped


def test_fake_adapter_shaped_result_validates_into_target_contract():
    result = validate_fake_adapter_structured_result(
        {
            "trace_id": "trace-adapter-001",
            "result": {
                "structured_payload": _valid_response_payload(text="Adapter mapped."),
            },
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Adapter mapped."


def test_fake_adapter_shaped_object_result_validates_into_target_contract():
    fake_result = FakeAdapterResult(
        trace_id="trace-adapter-002",
        result=FakeAdapterPayloadResult(
            structured_payload=_valid_response_payload(text="Object adapter mapped.")
        ),
    )

    result = validate_fake_adapter_structured_result(
        fake_result,
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    assert result.text == "Object adapter mapped."


def test_fake_adapter_shaped_missing_payload_returns_error_envelope():
    result = validate_fake_adapter_structured_result(
        {
            "trace_id": "trace-adapter-missing-001",
            "result": {},
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-adapter-missing-001"
    assert result.code == ErrorCode.VALIDATION_ERROR
    assert result.source == "provider_structured_output"
    assert result.details == {
        "target": "AssistantFinalResponse",
        "field": "structured_payload",
    }


def test_fake_adapter_shaped_malformed_payload_returns_error_envelope():
    result = validate_fake_adapter_structured_result(
        {
            "trace_id": "trace-adapter-malformed-001",
            "result": {
                "structured_payload": _valid_response_payload(text=""),
            },
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-adapter-malformed-001"
    assert result.details["target"] == "AssistantFinalResponse"
    assert result.details["errors"]


def test_fake_adapter_shaped_error_result_returns_error_envelope():
    result = validate_fake_adapter_structured_result(
        {
            "trace_id": "trace-adapter-error-001",
            "error": {"message": "fake adapter result unavailable"},
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-adapter-error-001"
    assert result.error_id == "structured-output-adapter-result-error"
    assert result.code == ErrorCode.VALIDATION_ERROR
    assert result.source == "provider_structured_output"
    assert result.details == {
        "target": "AssistantFinalResponse",
        "field": "error",
    }


def test_fake_adapter_shaped_mapping_preserves_trace_id_for_validation_errors():
    result = validate_fake_adapter_structured_result(
        {
            "trace_id": "trace-adapter-preserved-001",
            "result": {
                "structured_payload": _valid_response_payload(text=""),
            },
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, ErrorEnvelope)
    assert result.trace_id == "trace-adapter-preserved-001"


def test_fake_adapter_shaped_mapping_does_not_create_refs_or_response_ids():
    result = validate_fake_adapter_structured_result(
        {
            "trace_id": "trace-adapter-003",
            "result": {
                "structured_payload": _valid_response_payload(),
            },
        },
        AssistantFinalResponse,
    )

    assert isinstance(result, AssistantFinalResponse)
    dumped = result.model_dump()
    assert "provider_turn_refs" not in dumped
    response_id_key = "provider" + "_response_id"
    assert response_id_key not in dumped
