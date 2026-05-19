
from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityExecutionMode, CapabilityRuntimeModel, ToolRiskLevel, ToolSideEffectLevel


class RiskGovernanceDecision(CapabilityRuntimeModel):
    action: str = Field(..., min_length=1)
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    execution_mode: CapabilityExecutionMode
    requires_confirmation: bool
    hard_blocked: bool
    reason_code: str


class RiskGovernancePolicy(CapabilityRuntimeModel):
    policy_id: Literal["marvex.risk_based_governance"] = "marvex.risk_based_governance"

    @classmethod
    def default(cls) -> "RiskGovernancePolicy":
        return cls()

    def classify(self, action: str) -> RiskGovernanceDecision:
        lowered = action.lower()
        if any(marker in lowered for marker in ("malware", "steal credential", "credential theft", "exploit prompt injection", "prompt injection", "command injection", "exfiltrate", "unauthorized account", "bypass captcha", "anti-bot bypass", "stealth", "payment without consent", "checkout without consent", "override policy")):
            return RiskGovernanceDecision(action=action, risk_level=ToolRiskLevel.CRITICAL, side_effect_level=ToolSideEffectLevel.DESTRUCTIVE, execution_mode=CapabilityExecutionMode.DENIED, requires_confirmation=False, hard_blocked=True, reason_code="risk.hard_block_abuse")
        if any(marker in lowered for marker in ("write", "delete", "send", "post", "upload", "export", "install", "enable connector", "auto-fetch", "submit form", "click", "type sensitive", "long browser", "run command", "connect oauth", "private account")):
            return RiskGovernanceDecision(action=action, risk_level=ToolRiskLevel.HIGH, side_effect_level=ToolSideEffectLevel.DESTRUCTIVE if "delete" in lowered else ToolSideEffectLevel.WRITE_LOCAL, execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL, requires_confirmation=True, hard_blocked=False, reason_code="risk.requires_confirmation")
        if any(marker in lowered for marker in ("read", "list", "search", "inspect", "summarize", "extract", "memory_tree_traverse", "mcp.list_tools")):
            return RiskGovernanceDecision(action=action, risk_level=ToolRiskLevel.LOW, side_effect_level=ToolSideEffectLevel.READ_ONLY, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, requires_confirmation=False, hard_blocked=False, reason_code="risk.allowed_read_list_search")
        return RiskGovernanceDecision(action=action, risk_level=ToolRiskLevel.MEDIUM, side_effect_level=ToolSideEffectLevel.NONE, execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL, requires_confirmation=True, hard_blocked=False, reason_code="risk.unknown_requires_clarification")
