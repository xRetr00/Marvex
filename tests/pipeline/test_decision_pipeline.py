from packages.adapters.pipeline.decision_pipeline import DecisionPipeline
from packages.contracts.decision_pipeline_models import DecisionFinalAction
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import (
    PromptAssemblyReport,
    PromptBlock,
    PromptBlockType,
    PromptPlan,
)


class FakeRouter:
    def __init__(self, decision: IntentDecision, calls: list[str]) -> None:
        self._decision = decision
        self._calls = calls

    def decide_route(self, input_text: str) -> IntentDecision:
        self._calls.append(f"route:{input_text}")
        return self._decision


class FakeValidator:
    def __init__(self, result: IntentValidationResult, calls: list[str]) -> None:
        self._result = result
        self._calls = calls

    def validate(self, input_text: str, intent_decision: IntentDecision) -> IntentValidationResult:
        self._calls.append(f"validate:{intent_decision.route_family.value}")
        return self._result


class FakePolicy:
    def __init__(self, decision: PolicyDecision, calls: list[str]) -> None:
        self._decision = decision
        self._calls = calls

    def decide(self, intent_decision: IntentDecision) -> PolicyDecision:
        self._calls.append(f"policy:{intent_decision.route_family.value}")
        return self._decision


class FakeContextBuilder:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.policy_decisions: list[PolicyDecision] = []

    def build_prompt_plan(
        self,
        input_text: str,
        intent_decision: IntentDecision,
        policy_decision: PolicyDecision,
    ) -> tuple[PromptPlan, PromptAssemblyReport]:
        self.calls.append(f"context:{policy_decision.reason_code}")
        self.policy_decisions.append(policy_decision)
        block = PromptBlock(
            block_type=PromptBlockType.RESPONSE_CONTRACT,
            content="respond through declarative plan",
            reason_code="response.test",
            char_budget=100,
            included=True,
        )
        return (
            PromptPlan(
                route_family=intent_decision.route_family,
                blocks=[block],
                total_budget=100,
            ),
            PromptAssemblyReport(
                included_blocks=[PromptBlockType.RESPONSE_CONTRACT],
                suppressed_blocks=[],
                reason_codes=["response.test"],
                budget_used=len(block.content),
            ),
        )


def intent(route_family: RouteFamily = RouteFamily.DIRECT_ANSWER) -> IntentDecision:
    return IntentDecision(
        route_family=route_family,
        confidence=0.86,
        ambiguity_flag=False,
    )


def validation(
    *,
    accepted: bool = True,
    needs_clarification: bool = False,
    risk_level: IntentRiskLevel = IntentRiskLevel.LOW,
    reason_code: str = "validator.accepted",
) -> IntentValidationResult:
    return IntentValidationResult(
        accepted=accepted,
        needs_clarification=needs_clarification,
        risk_level=risk_level,
        reason_code=reason_code,
        corrected_route_family=None,
    )


def policy(
    *,
    allow: bool = True,
    clarify: bool = False,
    deny: bool = False,
    reason_code: str = "policy.allowed",
) -> PolicyDecision:
    return PolicyDecision(
        allow=allow,
        clarify=clarify,
        deny=deny,
        reason_code=reason_code,
    )


def pipeline_for(
    *,
    validator_result: IntentValidationResult,
    policy_decision: PolicyDecision,
    route_decision: IntentDecision | None = None,
    calls: list[str] | None = None,
    context_builder: FakeContextBuilder | None = None,
) -> tuple[DecisionPipeline, list[str], FakeContextBuilder]:
    call_log = calls if calls is not None else []
    context = context_builder or FakeContextBuilder(call_log)
    return (
        DecisionPipeline(
            router=FakeRouter(route_decision or intent(), call_log),
            validator=FakeValidator(validator_result, call_log),
            policy_gate=FakePolicy(policy_decision, call_log),
            context_builder=context,
        ),
        call_log,
        context,
    )


def test_successful_proceed_path_composes_all_components_in_order() -> None:
    pipeline, calls, _ = pipeline_for(
        validator_result=validation(),
        policy_decision=policy(),
    )

    result = pipeline.run("answer directly")

    assert calls == [
        "route:answer directly",
        "validate:direct_answer",
        "policy:direct_answer",
        "context:policy.allowed",
    ]
    assert result.final_action == DecisionFinalAction.PROCEED
    assert result.reason_code == "pipeline.proceed"
    assert result.prompt_plan.tool_surface_exposed == []


def test_validator_clarification_path_uses_effective_clarification_policy_for_context() -> None:
    pipeline, _, context = pipeline_for(
        validator_result=validation(
            accepted=False,
            needs_clarification=True,
            risk_level=IntentRiskLevel.MEDIUM,
            reason_code="validator.needs_clarification",
        ),
        policy_decision=policy(),
    )

    result = pipeline.run("that one")

    assert result.final_action == DecisionFinalAction.CLARIFY
    assert result.reason_code == "validator.needs_clarification"
    assert context.policy_decisions[-1] == PolicyDecision(
        allow=False,
        clarify=True,
        deny=False,
        reason_code="validator.needs_clarification",
    )


def test_policy_deny_path_takes_deny_precedence() -> None:
    pipeline, _, _ = pipeline_for(
        validator_result=validation(
            accepted=False,
            needs_clarification=True,
            risk_level=IntentRiskLevel.MEDIUM,
            reason_code="validator.needs_clarification",
        ),
        policy_decision=policy(
            allow=False,
            clarify=False,
            deny=True,
            reason_code="policy.denied",
        ),
    )

    result = pipeline.run("inspect local state")

    assert result.final_action == DecisionFinalAction.DENY
    assert result.reason_code == "policy.denied"


def test_policy_clarify_path_returns_clarify() -> None:
    pipeline, _, _ = pipeline_for(
        validator_result=validation(),
        policy_decision=policy(
            allow=False,
            clarify=True,
            deny=False,
            reason_code="policy.clarify_ambiguous_route",
        ),
    )

    result = pipeline.run("ambiguous")

    assert result.final_action == DecisionFinalAction.CLARIFY
    assert result.reason_code == "policy.clarify_ambiguous_route"
