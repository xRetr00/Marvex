import pytest
from pydantic import ValidationError

from packages.contracts.intent_models import RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult


def test_accepts_valid_low_risk_result() -> None:
    result = IntentValidationResult(
        accepted=True,
        needs_clarification=False,
        risk_level=IntentRiskLevel.LOW,
        reason_code="validator.accepted",
        corrected_route_family=None,
    )

    assert result.accepted is True
    assert result.needs_clarification is False
    assert result.corrected_route_family is None


def test_accepts_high_risk_misroute_with_corrected_route_family() -> None:
    result = IntentValidationResult(
        accepted=False,
        needs_clarification=False,
        risk_level=IntentRiskLevel.HIGH,
        reason_code="validator.likely_misroute",
        corrected_route_family=RouteFamily.CLARIFY,
    )

    assert result.risk_level == IntentRiskLevel.HIGH
    assert result.corrected_route_family == RouteFamily.CLARIFY


def test_rejects_accepted_and_needs_clarification_together() -> None:
    with pytest.raises(ValidationError, match="accepted result cannot need clarification"):
        IntentValidationResult(
            accepted=True,
            needs_clarification=True,
            risk_level=IntentRiskLevel.MEDIUM,
            reason_code="validator.invalid",
            corrected_route_family=None,
        )


def test_rejects_accepted_high_risk_result() -> None:
    with pytest.raises(ValidationError, match="accepted result cannot be high risk"):
        IntentValidationResult(
            accepted=True,
            needs_clarification=False,
            risk_level=IntentRiskLevel.HIGH,
            reason_code="validator.invalid",
            corrected_route_family=None,
        )


def test_rejects_invalid_risk_level_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        IntentValidationResult(
            accepted=False,
            needs_clarification=True,
            risk_level="severe",
            reason_code="validator.invalid",
            corrected_route_family=None,
            prompt="not allowed",
        )
