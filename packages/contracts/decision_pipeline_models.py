from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from packages.contracts.intent_models import ContractModel, IntentDecision, PolicyDecision
from packages.contracts.intent_validation_models import IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan


class DecisionFinalAction(str, Enum):
    PROCEED = "proceed"
    CLARIFY = "clarify"
    DENY = "deny"


class DecisionPipelineResult(ContractModel):
    intent_decision: IntentDecision
    intent_validation_result: IntentValidationResult
    policy_decision: PolicyDecision
    prompt_plan: PromptPlan
    prompt_assembly_report: PromptAssemblyReport
    final_action: DecisionFinalAction
    reason_code: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_empty_prompt_plan_surface(self) -> "DecisionPipelineResult":
        if self.prompt_plan.tool_surface_exposed:
            raise ValueError("prompt_plan.tool_surface_exposed must be empty")
        return self
