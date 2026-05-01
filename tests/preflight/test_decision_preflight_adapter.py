from packages.adapters.preflight.decision_preflight_adapter import DecisionPreflightAdapter
from packages.contracts.decision_pipeline_models import DecisionFinalAction, DecisionPipelineResult
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan


class FakeDecisionPipeline:
    def __init__(self, result: DecisionPipelineResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def run(self, input_text: str) -> DecisionPipelineResult:
        self.calls.append(input_text)
        return self.result


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


def test_disabled_preflight_does_not_run_pipeline() -> None:
    pipeline = FakeDecisionPipeline(decision_result())
    adapter = DecisionPreflightAdapter(decision_pipeline=pipeline)

    result = adapter.run("hello", enabled=False)

    assert pipeline.calls == []
    assert result.enabled is False
    assert result.observed is False
    assert result.final_action is None
    assert result.reason_code is None
    assert result.decision_pipeline_result is None
    assert result.blocking_applied is False


def test_enabled_preflight_runs_pipeline_once() -> None:
    pipeline = FakeDecisionPipeline(decision_result())
    adapter = DecisionPreflightAdapter(decision_pipeline=pipeline)

    result = adapter.run("hello", enabled=True)

    assert pipeline.calls == ["hello"]
    assert result.enabled is True
    assert result.observed is True
    assert result.final_action == DecisionFinalAction.PROCEED
    assert result.reason_code == "pipeline.proceed"
    assert result.decision_pipeline_result == pipeline.result
    assert result.blocking_applied is False


def test_clarify_result_remains_observe_only() -> None:
    adapter = DecisionPreflightAdapter(
        decision_pipeline=FakeDecisionPipeline(decision_result(DecisionFinalAction.CLARIFY))
    )

    result = adapter.run("ambiguous", enabled=True)

    assert result.final_action == DecisionFinalAction.CLARIFY
    assert result.observed is True
    assert result.blocking_applied is False


def test_deny_result_remains_observe_only() -> None:
    adapter = DecisionPreflightAdapter(
        decision_pipeline=FakeDecisionPipeline(decision_result(DecisionFinalAction.DENY))
    )

    result = adapter.run("blocked", enabled=True)

    assert result.final_action == DecisionFinalAction.DENY
    assert result.observed is True
    assert result.blocking_applied is False
