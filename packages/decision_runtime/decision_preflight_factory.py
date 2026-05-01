from __future__ import annotations

from typing import Any

from packages.adapters.preflight.decision_preflight_adapter import DecisionPreflightAdapter
from packages.contracts.decision_pipeline_models import DecisionPipelineResult
from packages.contracts.prompt_plan_models import PromptBlockType
from packages.contracts.turn_preflight_models import TurnPreflightResult
from packages.decision_runtime.decision_pipeline_factory import create_dev_decision_pipeline


def create_dev_turn_preflight() -> DecisionPreflightAdapter:
    return DecisionPreflightAdapter(decision_pipeline=create_dev_decision_pipeline())


def run_dev_turn_preflight(input_text: str, enabled: bool) -> dict[str, Any]:
    result = create_dev_turn_preflight().run(input_text, enabled=enabled)
    return _turn_preflight_payload(result)


def _turn_preflight_payload(result: TurnPreflightResult) -> dict[str, Any]:
    return {
        "enabled": result.enabled,
        "observed": result.observed,
        "final_action": result.final_action.value if result.final_action is not None else None,
        "reason_code": result.reason_code,
        "decision_pipeline_result": _decision_payload(result.decision_pipeline_result),
        "blocking_applied": result.blocking_applied,
    }


def _decision_payload(result: DecisionPipelineResult | None) -> dict[str, Any] | None:
    if result is None:
        return None

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
