from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.capability_runtime import AutonomyPolicy, PolicyDecision
from packages.capability_runtime.models import CapabilityRuntimeModel


class TurnRecoveryPolicy(CapabilityRuntimeModel):
    autonomy_policy: AutonomyPolicy
    provider_fallback_enabled: bool = True
    web_search_fallback_enabled: bool = True
    memory_fallback_enabled: bool = True
    clarification_enabled: bool = True


class SafeFailureProjection(CapabilityRuntimeModel):
    decision: str
    reason_code: str
    raw_failure_persisted: Literal[False] = False


class TurnFallbackDecision(CapabilityRuntimeModel):
    decision: str
    reason_code: str
    next_provider: str | None = None
    approval_required: bool = False
    raw_failure_persisted: Literal[False] = False

    def safe_projection(self) -> SafeFailureProjection:
        return SafeFailureProjection(decision=self.decision, reason_code=self.reason_code)


class ProviderFailureRecovery:
    def __init__(self, policy: TurnRecoveryPolicy) -> None:
        self._policy = policy

    def recover(self, *, reason_code: str, side_effectful: bool) -> TurnFallbackDecision:
        fallback = self._policy.autonomy_policy.provider_fallback.provider_fallback
        if side_effectful and fallback.value != "allow":
            return TurnFallbackDecision(decision="ask_before_provider_retry", reason_code="recovery.side_effect_retry_requires_policy", approval_required=True)
        if self._policy.provider_fallback_enabled and fallback.value == "allow":
            return TurnFallbackDecision(decision="fallback_provider", reason_code=reason_code)
        return TurnFallbackDecision(decision="provider_failure_terminal", reason_code=reason_code)


class ToolFailureRecovery:
    def __init__(self, policy: TurnRecoveryPolicy) -> None:
        self._policy = policy

    def recover(self, *, tool_name: str, side_effectful: bool) -> TurnFallbackDecision:
        if side_effectful:
            return TurnFallbackDecision(decision="do_not_repeat_side_effect", reason_code="recovery.side_effect_tool_not_repeated", approval_required=True)
        allowed = self._policy.autonomy_policy.mode.value == "auto_marvex"
        return TurnFallbackDecision(decision="retry_tool_once" if allowed else "ask_before_tool_retry", reason_code=f"recovery.tool_failure.{_safe_name(tool_name)}", approval_required=not allowed)


class WebSearchFallback:
    def __init__(self, policy: TurnRecoveryPolicy) -> None:
        self._policy = policy

    def recover(self, *, provider_chain: tuple[str, ...], failed_provider: str) -> TurnFallbackDecision:
        try:
            index = provider_chain.index(failed_provider)
        except ValueError:
            index = -1
        next_provider = provider_chain[index + 1] if index + 1 < len(provider_chain) else None
        if self._policy.web_search_fallback_enabled and next_provider is not None:
            return TurnFallbackDecision(decision="try_next_web_provider", reason_code="recovery.web_search_next_provider", next_provider=next_provider)
        return TurnFallbackDecision(decision="evidence_missing", reason_code="recovery.web_search_evidence_missing")


class MemoryRetrievalFallback:
    def __init__(self, policy: TurnRecoveryPolicy) -> None:
        self._policy = policy

    def recover(self, *, reason_code: str) -> TurnFallbackDecision:
        decision = "lexical_memory_search" if self._policy.memory_fallback_enabled else "memory_retrieval_failed"
        return TurnFallbackDecision(decision=decision, reason_code=reason_code)


class ClarificationFallback:
    def __init__(self, policy: TurnRecoveryPolicy) -> None:
        self._policy = policy

    def recover(self, *, input_summary: str) -> TurnFallbackDecision:
        return TurnFallbackDecision(decision="ask_clarification", reason_code="recovery.clarification_stop")


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in ".:-_" else "-" for character in value)[:80]
