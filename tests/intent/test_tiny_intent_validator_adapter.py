import pytest
from pydantic import ValidationError

from packages.adapters.intent.tiny_intent_validator_adapter import (
    AdapterModelUnavailableError,
    TinyIntentValidatorAdapter,
)
from packages.contracts.intent_models import IntentDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult


class FakeTinyModelClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def validate_intent(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return self.response


def intent(route_family: RouteFamily, confidence: float = 0.86, ambiguous: bool = False) -> IntentDecision:
    return IntentDecision(
        route_family=route_family,
        confidence=confidence,
        ambiguity_flag=ambiguous,
    )


def test_accepts_high_confidence_route_from_injected_tiny_model_client() -> None:
    client = FakeTinyModelClient(
        {
            "accepted": True,
            "needs_clarification": False,
            "risk_level": "low",
            "reason_code": "validator.accepted_high_confidence",
            "corrected_route_family": None,
        }
    )
    adapter = TinyIntentValidatorAdapter(model_client=client)

    result = adapter.validate("what is in this file?", intent(RouteFamily.DIRECT_ANSWER))

    assert result == IntentValidationResult(
        accepted=True,
        needs_clarification=False,
        risk_level=IntentRiskLevel.LOW,
        reason_code="validator.accepted_high_confidence",
        corrected_route_family=None,
    )
    assert client.calls == [
        {
            "input_text": "what is in this file?",
            "route_family": "direct_answer",
            "confidence": 0.86,
            "ambiguity_flag": False,
        }
    ]


def test_flags_low_confidence_ambiguity() -> None:
    client = FakeTinyModelClient(
        {
            "accepted": False,
            "needs_clarification": True,
            "risk_level": "medium",
            "reason_code": "validator.low_confidence_ambiguous",
            "corrected_route_family": "clarify",
        }
    )
    adapter = TinyIntentValidatorAdapter(model_client=client)

    result = adapter.validate("that one", intent(RouteFamily.GROUNDED_LOOKUP, confidence=0.31, ambiguous=True))

    assert result.accepted is False
    assert result.needs_clarification is True
    assert result.risk_level == IntentRiskLevel.MEDIUM
    assert result.corrected_route_family == RouteFamily.CLARIFY


def test_flags_route_mismatch_with_corrected_route_family() -> None:
    client = FakeTinyModelClient(
        {
            "accepted": False,
            "needs_clarification": False,
            "risk_level": "high",
            "reason_code": "validator.likely_misroute",
            "corrected_route_family": "grounded_lookup",
        }
    )
    adapter = TinyIntentValidatorAdapter(model_client=client)

    result = adapter.validate(
        "look up the latest provider docs",
        intent(RouteFamily.DIRECT_ANSWER),
    )

    assert result.accepted is False
    assert result.needs_clarification is False
    assert result.risk_level == IntentRiskLevel.HIGH
    assert result.corrected_route_family == RouteFamily.GROUNDED_LOOKUP


def test_recommends_clarification_when_safer() -> None:
    client = FakeTinyModelClient(
        {
            "accepted": False,
            "needs_clarification": True,
            "risk_level": "high",
            "reason_code": "validator.clarification_safer",
            "corrected_route_family": "clarify",
        }
    )
    adapter = TinyIntentValidatorAdapter(model_client=client)

    result = adapter.validate("do the thing from before", intent(RouteFamily.LOCAL_STATE_INSPECTION))

    assert result.needs_clarification is True
    assert result.corrected_route_family == RouteFamily.CLARIFY


def test_rejects_invalid_validation_shape_from_model() -> None:
    client = FakeTinyModelClient(
        {
            "accepted": True,
            "needs_clarification": True,
            "risk_level": "high",
            "reason_code": "validator.invalid",
            "corrected_route_family": None,
        }
    )
    adapter = TinyIntentValidatorAdapter(model_client=client)

    with pytest.raises(ValidationError):
        adapter.validate("ambiguous", intent(RouteFamily.CLARIFY, ambiguous=True))


def test_optional_real_model_constructor_reports_structured_unavailable_error() -> None:
    def missing_importer(module_name: str) -> object:
        raise ModuleNotFoundError(module_name)

    with pytest.raises(AdapterModelUnavailableError) as error:
        TinyIntentValidatorAdapter.from_library(importer=missing_importer)

    assert error.value.adapter_name == "TinyIntentValidatorAdapter"
    assert error.value.model_name == "LiquidAI/LFM2.5-350M"
    assert error.value.reason_code == "model_unavailable"


def test_payload_excludes_prompt_tools_mcp_memory_and_provider_schema() -> None:
    client = FakeTinyModelClient(
        {
            "accepted": True,
            "needs_clarification": False,
            "risk_level": "low",
            "reason_code": "validator.accepted",
            "corrected_route_family": None,
        }
    )
    adapter = TinyIntentValidatorAdapter(model_client=client)

    adapter.validate("simple", intent(RouteFamily.DIRECT_ANSWER))

    assert set(client.calls[0]) == {
        "input_text",
        "route_family",
        "confidence",
        "ambiguity_flag",
    }
