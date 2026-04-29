from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.prompt_plan_models import (
    PromptAssemblyReport,
    PromptBlock,
    PromptBlockType,
    PromptPlan,
)


@dataclass(frozen=True)
class ContextBuilder:
    total_budget: int = 1000
    identity_budget: int = 80
    user_input_budget: int = 600
    placeholder_budget: int = 0
    response_contract_budget: int = 220
    clarification_evidence_budget: int = 120

    def build_prompt_plan(
        self,
        input_text: str,
        intent_decision: IntentDecision,
        policy_decision: PolicyDecision,
    ) -> tuple[PromptPlan, PromptAssemblyReport]:
        blocks = [
            self._identity_block(),
            self._user_input_block(input_text, policy_decision),
            self._suppressed_placeholder(PromptBlockType.VERIFIED_EVIDENCE, "evidence.not_available_task_035"),
            self._suppressed_placeholder(PromptBlockType.SELECTED_MEMORY, "memory.not_available_task_035"),
            self._suppressed_placeholder(PromptBlockType.SELECTED_TOOLS, "tools.not_available_task_035"),
            self._response_contract_block(intent_decision.route_family, policy_decision),
        ]
        blocks = self._enforce_total_budget(blocks)
        plan = PromptPlan(
            route_family=intent_decision.route_family,
            blocks=blocks,
            total_budget=self.total_budget,
        )
        return plan, self._report_for(blocks)

    def _identity_block(self) -> PromptBlock:
        return self._included_block(
            PromptBlockType.IDENTITY,
            "Marvex context plan. Use only included declarative blocks.",
            "identity.minimal",
            self.identity_budget,
        )

    def _user_input_block(self, input_text: str, policy_decision: PolicyDecision) -> PromptBlock:
        if policy_decision.deny:
            return self._suppressed_block(
                PromptBlockType.USER_INPUT,
                "input.suppressed_policy_denied",
                self.user_input_budget,
            )

        if policy_decision.clarify:
            return self._clarification_evidence_block(input_text)

        if len(input_text) > self.user_input_budget:
            return self._suppressed_block(
                PromptBlockType.USER_INPUT,
                "input.suppressed_over_budget",
                self.user_input_budget,
            )

        return self._included_block(
            PromptBlockType.USER_INPUT,
            input_text,
            "input.budgeted_user_input",
            self.user_input_budget,
        )

    def _clarification_evidence_block(self, input_text: str) -> PromptBlock:
        suffix = "[redacted]"
        if self.clarification_evidence_budget <= len(suffix):
            return self._suppressed_block(
                PromptBlockType.USER_INPUT,
                "input.suppressed_clarification_budget",
                self.clarification_evidence_budget,
            )

        visible_budget = self.clarification_evidence_budget - len(suffix)
        content = f"{input_text[:visible_budget]}{suffix}"
        return self._included_block(
            PromptBlockType.USER_INPUT,
            content,
            "input.redacted_clarification_evidence",
            self.clarification_evidence_budget,
        )

    def _response_contract_block(
        self,
        route_family: RouteFamily,
        policy_decision: PolicyDecision,
    ) -> PromptBlock:
        reason_code, content = self._response_contract_for(route_family, policy_decision)
        return self._included_block(
            PromptBlockType.RESPONSE_CONTRACT,
            content,
            reason_code,
            self.response_contract_budget,
        )

    def _response_contract_for(
        self,
        route_family: RouteFamily,
        policy_decision: PolicyDecision,
    ) -> tuple[str, str]:
        if policy_decision.deny:
            return (
                "response.policy_denied",
                "Return a concise policy denial using only the policy reason code.",
            )

        if policy_decision.clarify or route_family == RouteFamily.CLARIFY:
            return (
                "response.clarify",
                "Ask one concise clarification question. Do not answer the task.",
            )

        contracts = {
            RouteFamily.DIRECT_ANSWER: (
                "response.direct_answer",
                "Answer directly and briefly from the included user input block.",
            ),
            RouteFamily.GROUNDED_LOOKUP: (
                "response.grounded_lookup",
                "Prepare a lookup-oriented answer plan. Require verified evidence before final claims.",
            ),
            RouteFamily.LOCAL_STATE_INSPECTION: (
                "response.local_state_inspection",
                "Prepare a minimal local-state inspection answer plan without exposing tools.",
            ),
        }
        return contracts[route_family]

    def _suppressed_placeholder(self, block_type: PromptBlockType, reason_code: str) -> PromptBlock:
        return self._suppressed_block(block_type, reason_code, self.placeholder_budget)

    def _included_block(
        self,
        block_type: PromptBlockType,
        content: str,
        reason_code: str,
        char_budget: int,
    ) -> PromptBlock:
        if len(content) > char_budget:
            return self._suppressed_block(
                block_type,
                f"{reason_code}.suppressed_block_budget",
                char_budget,
            )

        return PromptBlock(
            block_type=block_type,
            content=content,
            reason_code=reason_code,
            char_budget=char_budget,
            included=True,
        )

    def _suppressed_block(
        self,
        block_type: PromptBlockType,
        reason_code: str,
        char_budget: int,
    ) -> PromptBlock:
        return PromptBlock(
            block_type=block_type,
            content="",
            reason_code=reason_code,
            char_budget=char_budget,
            included=False,
        )

    def _enforce_total_budget(self, blocks: list[PromptBlock]) -> list[PromptBlock]:
        budget_used = 0
        budgeted_blocks = []
        for block in blocks:
            if not block.included:
                budgeted_blocks.append(block)
                continue

            content_size = len(block.content)
            if budget_used + content_size <= self.total_budget:
                budget_used += content_size
                budgeted_blocks.append(block)
                continue

            budgeted_blocks.append(
                self._suppressed_block(
                    block.block_type,
                    f"{block.reason_code}.suppressed_total_budget",
                    block.char_budget,
                )
            )
        return budgeted_blocks

    def _report_for(self, blocks: list[PromptBlock]) -> PromptAssemblyReport:
        return PromptAssemblyReport(
            included_blocks=[block.block_type for block in blocks if block.included],
            suppressed_blocks=[block.block_type for block in blocks if not block.included],
            reason_codes=[block.reason_code for block in blocks],
            budget_used=sum(len(block.content) for block in blocks if block.included),
        )
