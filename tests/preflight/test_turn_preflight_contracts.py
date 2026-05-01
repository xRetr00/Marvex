import pytest
from pydantic import ValidationError

from packages.contracts.decision_pipeline_models import DecisionFinalAction, DecisionPipelineResult
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan
from packages.contracts.turn_preflight_models import TurnPreflightResult


def decision_result(final_action: DecisionFinalAction = DecisionFinalAction.PROCEED) -> DecisionPipelineResult:
    return DecisionPipelineResult(
        intent_decision=IntentDecision(
            route_family=RouteFamily.DIRECT_ANSWER,
            confidence=0.9,
            ambiguity_flag=False,
        ),
        intent_validation_result=IntentValidationResult(
            accepted=final_action == DecisionFinalAction.PROCEED,
            needs_clarification=final_action == DecisionFinalAction.CLARIFY,
            risk_level=IntentRiskLevel.LOW if final_action == DecisionFinalAction.PROCEED else IntentRiskLevel.MEDIUM,
            reason_code="validator.test",
            corrected_route_family=None,
        ),
        policy_decision=PolicyDecision(
            allow=final_action == DecisionFinalAction.PROCEED,
            clarify=final_action == DecisionFinalAction.CLARIFY,
            deny=final_action == DecisionFinalAction.DENY,
            reason_code="policy.test",
        ),
        prompt_plan=PromptPlan(
            route_family=RouteFamily.DIRECT_ANSWER,
            blocks=[],
            total_budget=0,
        ),
        prompt_assembly_report=PromptAssemblyReport(
            included_blocks=[],
            suppressed_blocks=[],
            reason_codes=[],
            budget_used=0,
        ),
        final_action=final_action,
        reason_code=f"pipeline.{final_action.value}",
    )


def test_disabled_preflight_result_has_no_observation() -> None:
    result = TurnPreflightResult(
        enabled=False,
        observed=False,
        final_action=None,
        reason_code=None,
        decision_pipeline_result=None,
        blocking_applied=False,
    )

    assert result.enabled is False
    assert result.observed is False
    assert result.final_action is None
    assert result.reason_code is None
    assert result.decision_pipeline_result is None
    assert result.blocking_applied is False


def test_observed_preflight_result_contains_decision_result() -> None:
    result = TurnPreflightResult(
        enabled=True,
        observed=True,
        final_action=DecisionFinalAction.PROCEED,
        reason_code="pipeline.proceed",
        decision_pipeline_result=decision_result(),
        blocking_applied=False,
    )

    assert result.enabled is True
    assert result.observed is True
    assert result.final_action == DecisionFinalAction.PROCEED
    assert result.decision_pipeline_result is not None


def test_rejects_blocking_applied_true() -> None:
    with pytest.raises(ValidationError, match="blocking_applied must remain false"):
        TurnPreflightResult(
            enabled=True,
            observed=True,
            final_action=DecisionFinalAction.DENY,
            reason_code="policy.denied",
            decision_pipeline_result=decision_result(DecisionFinalAction.DENY),
            blocking_applied=True,
        )


def test_disabled_preflight_must_have_null_decision_fields() -> None:
    with pytest.raises(ValidationError, match="disabled preflight must not include decision output"):
        TurnPreflightResult(
            enabled=False,
            observed=False,
            final_action=DecisionFinalAction.PROCEED,
            reason_code="pipeline.proceed",
            decision_pipeline_result=decision_result(),
            blocking_applied=False,
        )


def test_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TurnPreflightResult(
            enabled=False,
            observed=False,
            final_action=None,
            reason_code=None,
            decision_pipeline_result=None,
            blocking_applied=False,
            rendered_prompt="not allowed",
        )
