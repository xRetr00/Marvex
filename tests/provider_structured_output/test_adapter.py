from dataclasses import dataclass

from packages.contracts import AssistantFinalResponse, ErrorCode, ErrorEnvelope
from packages.provider_structured_output import validate_structured_payload


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
