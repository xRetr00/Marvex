from packages.assistant_turn_integration.recovery import (
    ClarificationFallback,
    MemoryRetrievalFallback,
    ProviderFailureRecovery,
    ToolFailureRecovery,
    TurnRecoveryPolicy,
    WebSearchFallback,
)
from packages.capability_runtime import AutonomyMode, AutonomyPolicy


def test_turn_recovery_selects_safe_fallbacks_for_provider_web_memory_and_clarification() -> None:
    policy = TurnRecoveryPolicy(autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX))

    provider = ProviderFailureRecovery(policy).recover(reason_code="provider.timeout", side_effectful=False)
    web = WebSearchFallback(policy).recover(provider_chain=("searxng", "ddgs"), failed_provider="searxng")
    memory = MemoryRetrievalFallback(policy).recover(reason_code="semantic_memory_failed")
    clarification = ClarificationFallback(policy).recover(input_summary="do it")

    assert provider.decision == "fallback_provider"
    assert provider.safe_projection().raw_failure_persisted is False
    assert web.decision == "try_next_web_provider"
    assert web.next_provider == "ddgs"
    assert memory.decision == "lexical_memory_search"
    assert clarification.decision == "ask_clarification"


def test_side_effect_tool_failure_does_not_auto_repeat_without_policy_allowance() -> None:
    ask_policy = TurnRecoveryPolicy(autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY))
    auto_policy = TurnRecoveryPolicy(autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX))

    ask_decision = ToolFailureRecovery(ask_policy).recover(tool_name="browser.click", side_effectful=True)
    auto_decision = ToolFailureRecovery(auto_policy).recover(tool_name="browser.extract_text", side_effectful=False)

    assert ask_decision.decision == "do_not_repeat_side_effect"
    assert ask_decision.approval_required is True
    assert auto_decision.decision == "retry_tool_once"
    assert auto_decision.approval_required is False


def test_web_search_fallback_reports_evidence_missing_after_provider_chain_exhaustion() -> None:
    policy = TurnRecoveryPolicy(autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX))

    decision = WebSearchFallback(policy).recover(provider_chain=("searxng", "ddgs"), failed_provider="ddgs")

    assert decision.decision == "evidence_missing"
    assert decision.next_provider is None
    assert decision.safe_projection().raw_failure_persisted is False
