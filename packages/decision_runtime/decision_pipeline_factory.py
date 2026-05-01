from __future__ import annotations

from typing import Any

from packages.adapters.context.context_builder import ContextBuilder
from packages.adapters.pipeline.decision_pipeline import DecisionPipeline
from packages.contracts.decision_pipeline_models import DecisionPipelineResult
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import PromptBlockType


def create_decision_pipeline(
    pipeline_cls: type,
    router: Any,
    validator: Any,
    policy_gate: Any,
    context_builder: Any,
) -> Any:
    return pipeline_cls(
        router=router,
        validator=validator,
        policy_gate=policy_gate,
        context_builder=context_builder,
    )


def create_dev_decision_pipeline() -> DecisionPipeline:
    return create_decision_pipeline(
        pipeline_cls=DecisionPipeline,
        router=_DevRouter(),
        validator=_DevValidator(),
        policy_gate=_DevPolicyGate(),
        context_builder=ContextBuilder(),
    )


def run_dev_decision_pipeline(input_text: str) -> dict[str, Any]:
    result = create_dev_decision_pipeline().run(input_text)
    return _decision_payload(result)


class _DevRouter:
    def decide_route(self, input_text: str) -> IntentDecision:
        empty = input_text.strip() == ""
        return {
            True: IntentDecision(
                route_family=RouteFamily.CLARIFY,
                confidence=0.2,
                ambiguity_flag=True,
            ),
            False: IntentDecision(
                route_family=RouteFamily.DIRECT_ANSWER,
                confidence=0.9,
                ambiguity_flag=False,
            ),
        }[empty]


class _DevValidator:
    def validate(self, input_text: str, intent_decision: IntentDecision) -> IntentValidationResult:
        clarify = intent_decision.ambiguity_flag or intent_decision.route_family == RouteFamily.CLARIFY
        return {
            True: IntentValidationResult(
                accepted=False,
                needs_clarification=True,
                risk_level=IntentRiskLevel.MEDIUM,
                reason_code="validator.dev_clarify",
                corrected_route_family=RouteFamily.CLARIFY,
            ),
            False: IntentValidationResult(
                accepted=True,
                needs_clarification=False,
                risk_level=IntentRiskLevel.LOW,
                reason_code="validator.dev_accepted",
                corrected_route_family=None,
            ),
        }[clarify]


class _DevPolicyGate:
    def decide(self, intent_decision: IntentDecision) -> PolicyDecision:
        clarify = intent_decision.route_family == RouteFamily.CLARIFY
        return {
            True: PolicyDecision(
                allow=False,
                clarify=True,
                deny=False,
                reason_code="policy.dev_clarify",
            ),
            False: PolicyDecision(
                allow=True,
                clarify=False,
                deny=False,
                reason_code="policy.dev_allowed",
            ),
        }[clarify]


def _decision_payload(result: DecisionPipelineResult) -> dict[str, Any]:
    return {
        "final_action": result.final_action.value,
        "reason_code": result.reason_code,
        "intent_decision": result.intent_decision.model_dump(mode="json"),
        "intent_validation_result": result.intent_validation_result.model_dump(mode="json"),
        "policy_decision": result.policy_decision.model_dump(mode="json"),
        "prompt_plan": _prompt_plan_summary(result),
        "prompt_assembly_report": _assembly_report_summary(result),
    }


def _prompt_plan_summary(result: DecisionPipelineResult) -> dict[str, Any]:
    plan = result.prompt_plan
    included = tuple(map(lambda block: block.block_type, filter(lambda block: block.included, plan.blocks)))
    suppressed = tuple(filter(lambda block: not block.included, plan.blocks))
    return {
        "route_family": plan.route_family.value,
        "block_count": len(plan.blocks),
        "included_blocks": _block_type_values(included),
        "suppressed_block_count": len(suppressed),
        "total_budget": plan.total_budget,
        "budget_used": result.prompt_assembly_report.budget_used,
        "tool_surface_exposed": plan.tool_surface_exposed,
    }


def _block_type_values(block_types: tuple[PromptBlockType, ...] | list[PromptBlockType]) -> list[str]:
    return list(map(lambda block_type: block_type.value, block_types))


def _assembly_report_summary(result: DecisionPipelineResult) -> dict[str, Any]:
    report = result.prompt_assembly_report
    return {
        "included_blocks": _block_type_values(report.included_blocks),
        "suppressed_block_count": len(report.suppressed_blocks),
        "reason_code_count": len(report.reason_codes),
        "budget_used": report.budget_used,
    }
