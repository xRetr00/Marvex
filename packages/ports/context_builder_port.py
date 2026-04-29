from __future__ import annotations

from typing import Protocol

from packages.contracts.intent_models import IntentDecision, PolicyDecision
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan


class ContextBuilderPort(Protocol):
    def build_prompt_plan(
        self,
        input_text: str,
        intent_decision: IntentDecision,
        policy_decision: PolicyDecision,
    ) -> tuple[PromptPlan, PromptAssemblyReport]:
        ...
