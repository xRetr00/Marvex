import pytest
from pydantic import ValidationError

from packages.adapters.pipeline.decision_pipeline import DecisionPipeline
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan


class StaticRouter:
    def decide_route(self, input_text: str) -> IntentDecision:
        return IntentDecision(
            route_family=RouteFamily.DIRECT_ANSWER,
            confidence=0.88,
            ambiguity_flag=False,
        )


class StaticPolicy:
    def decide(self, intent_decision: IntentDecision) -> PolicyDecision:
        return PolicyDecision(
            allow=True,
            clarify=False,
            deny=False,
            reason_code="policy.allowed",
        )


class StaticContextBuilder:
    def __init__(self, prompt_plan: object) -> None:
        self._prompt_plan = prompt_plan

    def build_prompt_plan(
        self,
        input_text: str,
        intent_decision: IntentDecision,
        policy_decision: PolicyDecision,
    ) -> tuple[object, PromptAssemblyReport]:
        return (
            self._prompt_plan,
            PromptAssemblyReport(
                included_blocks=[],
                suppressed_blocks=[],
                reason_codes=[],
                budget_used=0,
            ),
        )


class InvalidValidator:
    def validate(self, input_text: str, intent_decision: IntentDecision) -> dict[str, object]:
        return {
            "accepted": True,
            "needs_clarification": True,
            "risk_level": "high",
            "reason_code": "validator.invalid",
            "corrected_route_family": None,
        }


class AcceptedValidator:
    def validate(self, input_text: str, intent_decision: IntentDecision) -> IntentValidationResult:
        return IntentValidationResult(
            accepted=True,
            needs_clarification=False,
            risk_level=IntentRiskLevel.LOW,
            reason_code="validator.accepted",
            corrected_route_family=None,
        )


def test_invalid_validator_output_fails_closed() -> None:
    pipeline = DecisionPipeline(
        router=StaticRouter(),
        validator=InvalidValidator(),
        policy_gate=StaticPolicy(),
        context_builder=StaticContextBuilder(PromptPlan(route_family=RouteFamily.DIRECT_ANSWER, blocks=[], total_budget=0)),
    )

    with pytest.raises(ValidationError):
        pipeline.run("input")


def test_invalid_prompt_plan_with_tool_surface_fails_closed() -> None:
    invalid_prompt_plan = {
        "route_family": "direct_answer",
        "blocks": [],
        "total_budget": 100,
        "tool_surface_exposed": ["provider_builtin_tools"],
    }
    pipeline = DecisionPipeline(
        router=StaticRouter(),
        validator=AcceptedValidator(),
        policy_gate=StaticPolicy(),
        context_builder=StaticContextBuilder(invalid_prompt_plan),
    )

    with pytest.raises(ValidationError, match="tool_surface_exposed must stay empty"):
        pipeline.run("input")


def test_pipeline_result_and_prompt_plan_have_no_rendered_prompt_field() -> None:
    pipeline = DecisionPipeline(
        router=StaticRouter(),
        validator=AcceptedValidator(),
        policy_gate=StaticPolicy(),
        context_builder=StaticContextBuilder(
            PromptPlan(
                route_family=RouteFamily.DIRECT_ANSWER,
                blocks=[],
                total_budget=0,
            )
        ),
    )

    result = pipeline.run("input")

    assert "prompt" not in result.model_dump()
    assert "rendered_prompt" not in result.model_dump()
    assert "prompt" not in result.prompt_plan.model_dump()
    assert "rendered_prompt" not in result.prompt_plan.model_dump()
