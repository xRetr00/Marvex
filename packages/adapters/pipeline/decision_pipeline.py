from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.decision_pipeline_models import DecisionFinalAction, DecisionPipelineResult
from packages.contracts.intent_models import IntentDecision, PolicyDecision
from packages.contracts.intent_validation_models import IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan
from packages.ports.context_builder_port import ContextBuilderPort
from packages.ports.intent_router_port import IntentRouterPort
from packages.ports.intent_validator_port import IntentValidatorPort
from packages.ports.policy_gate_port import PolicyGatePort


@dataclass(frozen=True)
class DecisionPipeline:
    router: IntentRouterPort
    validator: IntentValidatorPort
    policy_gate: PolicyGatePort
    context_builder: ContextBuilderPort

    def run(self, input_text: str) -> DecisionPipelineResult:
        intent_decision = IntentDecision.model_validate(self.router.decide_route(input_text))
        validation_result = IntentValidationResult.model_validate(
            self.validator.validate(input_text, intent_decision)
        )
        policy_decision = PolicyDecision.model_validate(self.policy_gate.decide(intent_decision))
        final_action, reason_code, context_policy = self._final_decision(
            validation_result,
            policy_decision,
        )
        prompt_plan, assembly_report = self.context_builder.build_prompt_plan(
            input_text,
            intent_decision,
            context_policy,
        )

        return DecisionPipelineResult(
            intent_decision=intent_decision,
            intent_validation_result=validation_result,
            policy_decision=policy_decision,
            prompt_plan=PromptPlan.model_validate(prompt_plan),
            prompt_assembly_report=PromptAssemblyReport.model_validate(assembly_report),
            final_action=final_action,
            reason_code=reason_code,
        )

    @staticmethod
    def _final_decision(
        validation_result: IntentValidationResult,
        policy_decision: PolicyDecision,
    ) -> tuple[DecisionFinalAction, str, PolicyDecision]:
        if policy_decision.deny:
            return DecisionFinalAction.DENY, policy_decision.reason_code, policy_decision

        if validation_result.needs_clarification or not validation_result.accepted:
            clarification_policy = PolicyDecision(
                allow=False,
                clarify=True,
                deny=False,
                reason_code=validation_result.reason_code,
            )
            return DecisionFinalAction.CLARIFY, validation_result.reason_code, clarification_policy

        if policy_decision.clarify:
            return DecisionFinalAction.CLARIFY, policy_decision.reason_code, policy_decision

        return DecisionFinalAction.PROCEED, "pipeline.proceed", policy_decision
