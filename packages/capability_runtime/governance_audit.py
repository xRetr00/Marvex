from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel, ToolRiskLevel, ToolSideEffectLevel


class GovernanceDecisionType(str, Enum):
    ALLOW = "allow"
    APPROVAL_REQUIRED = "approval_required"
    DENY = "deny"
    QUARANTINE = "quarantine"
    HARD_BLOCK = "hard_block"


class GranularPermission(str, Enum):
    PUBLIC_READ = "public_read"
    MEMORY_READ = "memory_read"
    TRACE_READ = "trace_read"
    TOOL_LIST = "tool_list"
    WRITE_LOCAL = "write_local"
    SEND_EXTERNAL = "send_external"
    BROWSER_SIDE_EFFECT = "browser_side_effect"
    EXECUTE_COMMAND = "execute_command"
    CONNECT_ACCOUNT = "connect_account"
    ARBITRARY_EXECUTION = "arbitrary_execution"
    POLICY_OVERRIDE = "policy_override"


class GovernanceAction(CapabilityRuntimeModel):
    requested_action: str = Field(..., min_length=1, max_length=300)
    capability: str = Field(..., min_length=1, max_length=120)
    permission: GranularPermission
    user_approval_state: Literal["not_required", "pending", "approved", "denied", "cancelled"] = "not_required"


class GovernanceSafeProjection(CapabilityRuntimeModel):
    decision: GovernanceDecisionType
    reason_codes: tuple[str, ...]
    capability: str
    requested_action_summary: str
    required_permission: GranularPermission
    policy_source: str
    user_approval_state: str
    raw_payload_persisted: Literal[False] = False


class GovernanceDecision(CapabilityRuntimeModel):
    action: GovernanceAction
    decision: GovernanceDecisionType
    reason_codes: tuple[str, ...]
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    required_permission: GranularPermission
    policy_source: Literal["packages.capability_runtime.governance_audit"] = "packages.capability_runtime.governance_audit"
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> GovernanceSafeProjection:
        return GovernanceSafeProjection(
            decision=self.decision,
            reason_codes=self.reason_codes,
            capability=self.action.capability,
            requested_action_summary=self.action.requested_action[:120],
            required_permission=self.required_permission,
            policy_source=self.policy_source,
            user_approval_state=self.action.user_approval_state,
        )


def classify_governance_action(action: GovernanceAction) -> GovernanceDecision:
    lowered = action.requested_action.lower()
    if any(marker in lowered for marker in ("command injection", "exfiltrate", "credential theft", "steal credential", "malware", "bypass captcha", "anti-bot", "payment without", "checkout without")):
        return GovernanceDecision(action=action, decision=GovernanceDecisionType.HARD_BLOCK, reason_codes=("governance.hard_block.abuse",), risk_level=ToolRiskLevel.CRITICAL, side_effect_level=ToolSideEffectLevel.DESTRUCTIVE, required_permission=action.permission)
    if any(marker in lowered for marker in ("prompt injection", "policy override", "override policy", "exploit prompt")) or action.permission == GranularPermission.POLICY_OVERRIDE:
        return GovernanceDecision(action=action, decision=GovernanceDecisionType.QUARANTINE, reason_codes=("governance.quarantine.injection_or_policy_override",), risk_level=ToolRiskLevel.CRITICAL, side_effect_level=ToolSideEffectLevel.NONE, required_permission=action.permission)
    if action.permission in {GranularPermission.PUBLIC_READ, GranularPermission.MEMORY_READ, GranularPermission.TRACE_READ, GranularPermission.TOOL_LIST}:
        return GovernanceDecision(action=action, decision=GovernanceDecisionType.ALLOW, reason_codes=("governance.allow.read_list_search",), risk_level=ToolRiskLevel.LOW, side_effect_level=ToolSideEffectLevel.READ_ONLY, required_permission=action.permission)
    if action.permission in {GranularPermission.WRITE_LOCAL, GranularPermission.SEND_EXTERNAL, GranularPermission.BROWSER_SIDE_EFFECT, GranularPermission.EXECUTE_COMMAND, GranularPermission.CONNECT_ACCOUNT}:
        side_effect = ToolSideEffectLevel.BROWSER_ACTION if action.permission == GranularPermission.BROWSER_SIDE_EFFECT else ToolSideEffectLevel.WRITE_LOCAL
        if action.permission == GranularPermission.EXECUTE_COMMAND:
            side_effect = ToolSideEffectLevel.DESKTOP_ACTION
        return GovernanceDecision(action=action, decision=GovernanceDecisionType.APPROVAL_REQUIRED, reason_codes=("governance.approval_required.side_effect",), risk_level=ToolRiskLevel.HIGH, side_effect_level=side_effect, required_permission=action.permission)
    if action.permission == GranularPermission.ARBITRARY_EXECUTION:
        return GovernanceDecision(action=action, decision=GovernanceDecisionType.DENY, reason_codes=("governance.deny.arbitrary_execution",), risk_level=ToolRiskLevel.CRITICAL, side_effect_level=ToolSideEffectLevel.DESTRUCTIVE, required_permission=action.permission)
    return GovernanceDecision(action=action, decision=GovernanceDecisionType.APPROVAL_REQUIRED, reason_codes=("governance.approval_required.unknown",), risk_level=ToolRiskLevel.MEDIUM, side_effect_level=ToolSideEffectLevel.NONE, required_permission=action.permission)
