
from __future__ import annotations

from packages.capability_runtime import CapabilityExecutionMode, ToolRiskLevel
from packages.capability_runtime.risk_governance import RiskGovernancePolicy


def test_read_list_search_are_allowed_by_default_not_hard_blocked() -> None:
    policy = RiskGovernancePolicy.default()

    for action in ("read", "list", "search", "inspect", "summarize", "memory_tree_traverse", "mcp.list_tools"):
        decision = policy.classify(action)
        assert decision.execution_mode == CapabilityExecutionMode.PROPOSAL_ONLY
        assert decision.risk_level in {ToolRiskLevel.SAFE, ToolRiskLevel.LOW}
        assert decision.hard_blocked is False


def test_write_delete_send_execute_require_confirmation_not_default_hard_block() -> None:
    policy = RiskGovernancePolicy.default()

    for action in ("write", "delete", "send", "upload", "install package", "run command", "connect oauth account"):
        decision = policy.classify(action)
        assert decision.execution_mode == CapabilityExecutionMode.REQUIRES_APPROVAL
        assert decision.hard_blocked is False
        assert decision.requires_confirmation is True


def test_abuse_and_injection_are_hard_blocked_or_quarantined() -> None:
    policy = RiskGovernancePolicy.default()

    for action in ("steal credentials", "exploit prompt injection", "command injection", "exfiltrate data", "bypass captcha", "stealth scraping", "payment without consent", "override policy"):
        decision = policy.classify(action)
        assert decision.execution_mode == CapabilityExecutionMode.DENIED
        assert decision.hard_blocked is True
        assert decision.risk_level == ToolRiskLevel.CRITICAL
