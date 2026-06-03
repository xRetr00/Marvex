from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator

from packages.capability_runtime.models import CapabilityRuntimeModel, ToolRiskLevel


SCHEMA_VERSION = "1"


class AutonomyMode(str, Enum):
    LOCKED_DOWN = "locked_down"
    ASK_BEFORE_RISKY = "ask_before_risky"
    OWNER_SAFE = "owner_safe"
    AUTO_MARVEX = "auto_marvex"
    CUSTOM = "custom"


class ActionPermission(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"
    QUARANTINE = "quarantine"
    HARD_BLOCK = "hard_block"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    APPROVAL_REQUIRED = "approval_required"
    DENY = "deny"
    QUARANTINE = "quarantine"
    HARD_BLOCK = "hard_block"


class CapabilityPermissionMatrix(CapabilityRuntimeModel):
    read: ActionPermission = ActionPermission.ALLOW
    list: ActionPermission = ActionPermission.ALLOW
    search: ActionPermission = ActionPermission.ALLOW
    web_search: ActionPermission = ActionPermission.ALLOW
    public_page_read_extract: ActionPermission = ActionPermission.ALLOW
    browser_read_extract: ActionPermission = ActionPermission.ALLOW
    browser_click_type: ActionPermission = ActionPermission.ASK
    computer_actions: ActionPermission = ActionPermission.ASK
    mcp_list: ActionPermission = ActionPermission.ALLOW
    mcp_execute: ActionPermission = ActionPermission.ASK
    mcp_install_launch: ActionPermission = ActionPermission.ASK
    skills_use: ActionPermission = ActionPermission.ALLOW
    skills_update_create: ActionPermission = ActionPermission.ASK
    connectors_oauth: ActionPermission = ActionPermission.ASK
    live_oauth_sync: ActionPermission = ActionPermission.ASK
    auto_fetch: ActionPermission = ActionPermission.ASK
    memory_search: ActionPermission = ActionPermission.ALLOW
    semantic_memory_search: ActionPermission = ActionPermission.ALLOW
    memory_explicit_write: ActionPermission = ActionPermission.ALLOW
    memory_auto_write: ActionPermission = ActionPermission.ASK
    profile_write: ActionPermission = ActionPermission.ASK
    learning_mutation_candidates: ActionPermission = ActionPermission.ASK
    provider_retry_fallback: ActionPermission = ActionPermission.ALLOW
    file_read: ActionPermission = ActionPermission.ALLOW
    file_write: ActionPermission = ActionPermission.ASK
    file_delete: ActionPermission = ActionPermission.ASK
    external_upload_send: ActionPermission = ActionPermission.ASK
    shell_command_execution: ActionPermission = ActionPermission.ASK

    def as_projection(self) -> dict[str, ActionPermission]:
        return dict(self.model_dump(mode="python"))


class RiskOverridePolicy(CapabilityRuntimeModel):
    hard_block_blacklist_only: Literal[True] = True
    blacklist_reason_codes: tuple[str, ...] = (
        "policy.blacklist.malware",
        "policy.blacklist.credential_theft",
        "policy.blacklist.data_exfiltration",
        "policy.blacklist.prompt_injection_exploitation",
        "policy.blacklist.command_injection",
        "policy.blacklist.captcha_bypass",
        "policy.blacklist.stealth_abuse",
        "policy.blacklist.unauthorized_account_access",
        "policy.blacklist.illegal_destructive_abuse",
        "policy.blacklist.payment_without_consent",
    )


class UserApprovalPolicy(CapabilityRuntimeModel):
    ask_permissions_pause_execution: Literal[True] = True
    approval_required_reason_code: str = "policy.approval_required.user_controlled"


class AutoExecutionPolicy(CapabilityRuntimeModel):
    read_list_search_auto_allowed: Literal[True] = True
    side_effects_follow_matrix: Literal[True] = True


class AutoFetchPolicyBinding(CapabilityRuntimeModel):
    global_auto_fetch: ActionPermission = ActionPermission.ASK
    per_connector_policy_controlled: Literal[True] = True
    per_source_policy_controlled: Literal[True] = True
    untracked_background_sync_allowed: Literal[False] = False


class MemoryAutoWritePolicy(CapabilityRuntimeModel):
    memory_auto_write: ActionPermission = ActionPermission.ASK
    no_hidden_writes: Literal[True] = True


class ProfileWritePolicy(CapabilityRuntimeModel):
    profile_write: ActionPermission = ActionPermission.ASK
    explicit_user_signal_required: Literal[True] = True


class ConnectorSyncPolicy(CapabilityRuntimeModel):
    oauth_connect: ActionPermission = ActionPermission.ASK
    live_sync: ActionPermission = ActionPermission.ASK
    auto_fetch: ActionPermission = ActionPermission.ASK
    sync_modes: tuple[str, ...] = ("manual", "on_demand", "scheduled", "continuous_future_seam")


class MCPExecutionPolicy(CapabilityRuntimeModel):
    list_tools: ActionPermission = ActionPermission.ALLOW
    execute_tool: ActionPermission = ActionPermission.ASK
    install_or_launch: ActionPermission = ActionPermission.ASK
    allowlist_required: Literal[True] = True


class SkillExecutionPolicy(CapabilityRuntimeModel):
    use_skill: ActionPermission = ActionPermission.ALLOW
    update_or_create_skill: ActionPermission = ActionPermission.ASK
    silent_mutation_allowed: Literal[False] = False


class BrowserComputerPolicy(CapabilityRuntimeModel):
    read_extract: ActionPermission = ActionPermission.ALLOW
    click_type: ActionPermission = ActionPermission.ASK
    computer_actions: ActionPermission = ActionPermission.ASK
    captcha_bypass_allowed: Literal[False] = False
    credential_entry_allowed: Literal[False] = False


class FileOperationPolicy(CapabilityRuntimeModel):
    read_file: ActionPermission = ActionPermission.ALLOW
    write_file: ActionPermission = ActionPermission.ASK
    delete_file: ActionPermission = ActionPermission.ASK
    external_upload_send: ActionPermission = ActionPermission.ASK


class ProviderFallbackPolicy(CapabilityRuntimeModel):
    intent_fallback: ActionPermission = ActionPermission.ALLOW
    search_fallback: ActionPermission = ActionPermission.ALLOW
    retrieval_fallback: ActionPermission = ActionPermission.ALLOW
    provider_retry: ActionPermission = ActionPermission.ASK
    provider_fallback: ActionPermission = ActionPermission.ASK
    generic_model_router_implemented: Literal[False] = False


class LearningMutationPolicy(CapabilityRuntimeModel):
    candidate_create: ActionPermission = ActionPermission.ALLOW
    candidate_apply: ActionPermission = ActionPermission.ASK
    skill_candidate_apply: ActionPermission = ActionPermission.ASK
    preference_candidate_apply: ActionPermission = ActionPermission.ASK
    silent_policy_or_skill_mutation_allowed: Literal[False] = False


class AutonomyAction(CapabilityRuntimeModel):
    action: str = Field(..., min_length=1, max_length=300)
    resource_type: str = Field(..., min_length=1, max_length=80)
    capability: str = Field(..., min_length=1, max_length=80)
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    connector_id: str | None = Field(default=None, max_length=120)
    source_id: str | None = Field(default=None, max_length=120)
    safe_trace_ref: str | None = Field(default=None, max_length=120)
    user_approval_state: Literal["not_required", "pending", "approved", "denied", "cancelled"] = "not_required"
    timestamp: str = Field(default="policy_runtime_timestamp_unset", max_length=120)

    @field_validator("capability")
    @classmethod
    def _validate_capability(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("capability must be trimmed")
        return value


class PolicyDecisionAuditRecord(CapabilityRuntimeModel):
    decision_id: str
    schema_version: str = SCHEMA_VERSION
    autonomy_mode: AutonomyMode
    decision: PolicyDecision
    action: str
    resource_type: str
    capability: str
    connector_id: str | None = None
    source_id: str | None = None
    risk_level: ToolRiskLevel
    reason_codes: tuple[str, ...]
    required_permission: ActionPermission
    user_approval_state: str
    policy_source: str = "packages.capability_runtime.autonomy"
    timestamp: str
    safe_trace_ref: str | None = None
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class SafePolicyProjection(CapabilityRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    mode: AutonomyMode
    matrix: dict[str, ActionPermission]
    audit_records: tuple[PolicyDecisionAuditRecord, ...] = ()
    hard_block_blacklist_only: Literal[True] = True
    read_list_search_allowed_by_default: Literal[True] = True
    side_effects_policy_controlled: Literal[True] = True
    raw_payload_persisted: Literal[False] = False


class AutonomyPolicy(CapabilityRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    mode: AutonomyMode
    matrix: CapabilityPermissionMatrix
    risk_overrides: RiskOverridePolicy = Field(default_factory=RiskOverridePolicy)
    user_approval: UserApprovalPolicy = Field(default_factory=UserApprovalPolicy)
    auto_execution: AutoExecutionPolicy = Field(default_factory=AutoExecutionPolicy)
    auto_fetch_binding: AutoFetchPolicyBinding = Field(default_factory=AutoFetchPolicyBinding)
    memory_auto_write: MemoryAutoWritePolicy = Field(default_factory=MemoryAutoWritePolicy)
    profile_write: ProfileWritePolicy = Field(default_factory=ProfileWritePolicy)
    connector_sync: ConnectorSyncPolicy = Field(default_factory=ConnectorSyncPolicy)
    mcp_execution: MCPExecutionPolicy = Field(default_factory=MCPExecutionPolicy)
    skill_execution: SkillExecutionPolicy = Field(default_factory=SkillExecutionPolicy)
    browser_computer: BrowserComputerPolicy = Field(default_factory=BrowserComputerPolicy)
    file_operations: FileOperationPolicy = Field(default_factory=FileOperationPolicy)
    provider_fallback: ProviderFallbackPolicy = Field(default_factory=ProviderFallbackPolicy)
    learning_mutation: LearningMutationPolicy = Field(default_factory=LearningMutationPolicy)
    policy_source: str = "packages.capability_runtime.autonomy"

    @classmethod
    def for_mode(cls, mode: AutonomyMode) -> AutonomyPolicy:
        if mode == AutonomyMode.LOCKED_DOWN:
            return cls(mode=mode, matrix=_locked_down_matrix())
        if mode == AutonomyMode.AUTO_MARVEX:
            return cls(
                mode=mode,
                matrix=_auto_marvex_matrix(),
                auto_fetch_binding=AutoFetchPolicyBinding(global_auto_fetch=ActionPermission.ALLOW),
                memory_auto_write=MemoryAutoWritePolicy(memory_auto_write=ActionPermission.ALLOW),
                profile_write=ProfileWritePolicy(profile_write=ActionPermission.ALLOW),
                connector_sync=ConnectorSyncPolicy(oauth_connect=ActionPermission.ALLOW, live_sync=ActionPermission.ALLOW, auto_fetch=ActionPermission.ALLOW),
                mcp_execution=MCPExecutionPolicy(execute_tool=ActionPermission.ALLOW, install_or_launch=ActionPermission.ALLOW),
                skill_execution=SkillExecutionPolicy(update_or_create_skill=ActionPermission.ALLOW),
                browser_computer=BrowserComputerPolicy(click_type=ActionPermission.ALLOW, computer_actions=ActionPermission.ALLOW),
                file_operations=FileOperationPolicy(write_file=ActionPermission.ALLOW, delete_file=ActionPermission.ALLOW, external_upload_send=ActionPermission.ALLOW),
                provider_fallback=ProviderFallbackPolicy(provider_retry=ActionPermission.ALLOW, provider_fallback=ActionPermission.ALLOW),
                learning_mutation=LearningMutationPolicy(candidate_apply=ActionPermission.ALLOW, skill_candidate_apply=ActionPermission.ALLOW, preference_candidate_apply=ActionPermission.ALLOW),
            )
        if mode == AutonomyMode.OWNER_SAFE:
            return cls(
                mode=mode,
                matrix=_owner_safe_matrix(),
                memory_auto_write=MemoryAutoWritePolicy(memory_auto_write=ActionPermission.ASK),
                connector_sync=ConnectorSyncPolicy(oauth_connect=ActionPermission.ASK, live_sync=ActionPermission.ASK, auto_fetch=ActionPermission.ASK),
                mcp_execution=MCPExecutionPolicy(execute_tool=ActionPermission.ASK),
                skill_execution=SkillExecutionPolicy(update_or_create_skill=ActionPermission.ASK),
                provider_fallback=ProviderFallbackPolicy(provider_retry=ActionPermission.ASK, provider_fallback=ActionPermission.ASK),
                learning_mutation=LearningMutationPolicy(candidate_apply=ActionPermission.ASK, skill_candidate_apply=ActionPermission.ASK, preference_candidate_apply=ActionPermission.ASK),
            )
        if mode == AutonomyMode.CUSTOM:
            return cls.custom()
        return cls(mode=mode, matrix=_ask_before_risky_matrix())

    @classmethod
    def custom(cls) -> AutonomyPolicy:
        return cls(mode=AutonomyMode.CUSTOM, matrix=_ask_before_risky_matrix())

    def with_permissions(self, **permissions: ActionPermission) -> AutonomyPolicy:
        return self.model_copy(update={"mode": AutonomyMode.CUSTOM, "matrix": self.matrix.model_copy(update=permissions)})

    def safe_projection(self, *, recent_audit: tuple[PolicyDecisionAuditRecord, ...] = ()) -> SafePolicyProjection:
        return SafePolicyProjection(mode=self.mode, matrix=self.matrix.as_projection(), audit_records=recent_audit)


BLACKLIST_MARKERS: tuple[tuple[str, str], ...] = (
    ("malware", "policy.blacklist.malware"),
    ("credential theft", "policy.blacklist.credential_theft"),
    ("steal credential", "policy.blacklist.credential_theft"),
    ("prompt injection", "policy.blacklist.prompt_injection_exploitation"),
    ("command injection", "policy.blacklist.command_injection"),
    ("exfiltrate", "policy.blacklist.data_exfiltration"),
    ("data exfiltration", "policy.blacklist.data_exfiltration"),
    ("bypass captcha", "policy.blacklist.captcha_bypass"),
    ("anti-bot bypass", "policy.blacklist.captcha_bypass"),
    ("stealth scraping", "policy.blacklist.stealth_abuse"),
    ("unauthorized account", "policy.blacklist.unauthorized_account_access"),
    ("illegal destructive", "policy.blacklist.illegal_destructive_abuse"),
    ("payment without", "policy.blacklist.payment_without_consent"),
    ("checkout payment without", "policy.blacklist.payment_without_consent"),
)


CAPABILITY_ALIASES = {
    "browser_read": "browser_read_extract",
    "public_page_read": "public_page_read_extract",
    "mcp": "mcp_execute",
    "skill": "skills_use",
    "skill_update": "skills_update_create",
    "connector_sync": "live_oauth_sync",
    "oauth_sync": "live_oauth_sync",
    "profile": "profile_write",
    "learning_mutation": "learning_mutation_candidates",
    "retry_fallback": "provider_retry_fallback",
    "file": "file_read",
    "delete": "file_delete",
    "write": "file_write",
    "send": "external_upload_send",
    "shell": "shell_command_execution",
}


def evaluate_autonomy_action(policy: AutonomyPolicy, action: AutonomyAction) -> PolicyDecisionAuditRecord:
    blacklist = _blacklist_reason(action.action)
    if blacklist is not None:
        return _audit(policy, action, decision=PolicyDecision.HARD_BLOCK, required_permission=ActionPermission.HARD_BLOCK, reason_codes=(blacklist, "policy.hard_block.blacklist_only"), risk_level=ToolRiskLevel.CRITICAL)

    permission = _permission_for(policy, action.capability)
    if permission == ActionPermission.ALLOW:
        return _audit(policy, action, decision=PolicyDecision.ALLOW, required_permission=permission, reason_codes=("policy.matrix.allow",), risk_level=action.risk_level)
    if permission == ActionPermission.ASK:
        return _audit(policy, action, decision=PolicyDecision.APPROVAL_REQUIRED, required_permission=permission, reason_codes=("policy.matrix.ask", policy.user_approval.approval_required_reason_code), risk_level=max_risk(action.risk_level, ToolRiskLevel.MEDIUM))
    if permission == ActionPermission.QUARANTINE:
        return _audit(policy, action, decision=PolicyDecision.QUARANTINE, required_permission=permission, reason_codes=("policy.matrix.quarantine",), risk_level=ToolRiskLevel.CRITICAL)
    if permission == ActionPermission.HARD_BLOCK:
        return _audit(policy, action, decision=PolicyDecision.DENY, required_permission=permission, reason_codes=("policy.matrix.hard_block_downgraded.non_blacklist",), risk_level=ToolRiskLevel.HIGH)
    return _audit(policy, action, decision=PolicyDecision.DENY, required_permission=permission, reason_codes=("policy.matrix.deny",), risk_level=max_risk(action.risk_level, ToolRiskLevel.MEDIUM))


def _permission_for(policy: AutonomyPolicy, capability: str) -> ActionPermission:
    matrix = policy.matrix.as_projection()
    key = capability.strip()
    key = CAPABILITY_ALIASES.get(key, key)
    return matrix.get(key, ActionPermission.ASK)


def _audit(policy: AutonomyPolicy, action: AutonomyAction, *, decision: PolicyDecision, required_permission: ActionPermission, reason_codes: tuple[str, ...], risk_level: ToolRiskLevel) -> PolicyDecisionAuditRecord:
    return PolicyDecisionAuditRecord(
        decision_id=f"policy.{policy.mode.value}.{abs(hash((action.action, action.capability, decision.value))) % 1_000_000}",
        autonomy_mode=policy.mode,
        decision=decision,
        action=action.action[:120],
        resource_type=action.resource_type,
        capability=action.capability,
        connector_id=action.connector_id,
        source_id=action.source_id,
        risk_level=risk_level,
        reason_codes=reason_codes,
        required_permission=required_permission,
        user_approval_state=action.user_approval_state,
        timestamp=action.timestamp,
        safe_trace_ref=action.safe_trace_ref,
    )


def _blacklist_reason(text: str) -> str | None:
    lowered = text.lower()
    for marker, reason_code in BLACKLIST_MARKERS:
        if marker in lowered:
            return reason_code
    return None


def max_risk(left: ToolRiskLevel, right: ToolRiskLevel) -> ToolRiskLevel:
    order = {ToolRiskLevel.SAFE: 0, ToolRiskLevel.LOW: 1, ToolRiskLevel.MEDIUM: 2, ToolRiskLevel.HIGH: 3, ToolRiskLevel.CRITICAL: 4}
    return left if order[left] >= order[right] else right


def _locked_down_matrix() -> CapabilityPermissionMatrix:
    safe = _ask_before_risky_matrix()
    return safe.model_copy(update={
        "browser_click_type": ActionPermission.DENY,
        "computer_actions": ActionPermission.DENY,
        "mcp_execute": ActionPermission.DENY,
        "mcp_install_launch": ActionPermission.DENY,
        "skills_update_create": ActionPermission.DENY,
        "connectors_oauth": ActionPermission.DENY,
        "live_oauth_sync": ActionPermission.DENY,
        "auto_fetch": ActionPermission.DENY,
        "memory_auto_write": ActionPermission.DENY,
        "memory_explicit_write": ActionPermission.ALLOW,
        "profile_write": ActionPermission.DENY,
        "learning_mutation_candidates": ActionPermission.DENY,
        "provider_retry_fallback": ActionPermission.DENY,
        "file_write": ActionPermission.DENY,
        "file_delete": ActionPermission.DENY,
        "external_upload_send": ActionPermission.DENY,
        "shell_command_execution": ActionPermission.DENY,
    })


def _ask_before_risky_matrix() -> CapabilityPermissionMatrix:
    return CapabilityPermissionMatrix()


def _auto_marvex_matrix() -> CapabilityPermissionMatrix:
    return CapabilityPermissionMatrix(
        read=ActionPermission.ALLOW,
        list=ActionPermission.ALLOW,
        search=ActionPermission.ALLOW,
        web_search=ActionPermission.ALLOW,
        public_page_read_extract=ActionPermission.ALLOW,
        browser_read_extract=ActionPermission.ALLOW,
        browser_click_type=ActionPermission.ALLOW,
        computer_actions=ActionPermission.ALLOW,
        mcp_list=ActionPermission.ALLOW,
        mcp_execute=ActionPermission.ALLOW,
        mcp_install_launch=ActionPermission.ALLOW,
        skills_use=ActionPermission.ALLOW,
        skills_update_create=ActionPermission.ALLOW,
        connectors_oauth=ActionPermission.ALLOW,
        live_oauth_sync=ActionPermission.ALLOW,
        auto_fetch=ActionPermission.ALLOW,
        memory_search=ActionPermission.ALLOW,
        semantic_memory_search=ActionPermission.ALLOW,
        memory_explicit_write=ActionPermission.ALLOW,
        memory_auto_write=ActionPermission.ALLOW,
        profile_write=ActionPermission.ALLOW,
        learning_mutation_candidates=ActionPermission.ALLOW,
        provider_retry_fallback=ActionPermission.ALLOW,
        file_read=ActionPermission.ALLOW,
        file_write=ActionPermission.ALLOW,
        file_delete=ActionPermission.ALLOW,
        external_upload_send=ActionPermission.ALLOW,
        shell_command_execution=ActionPermission.ALLOW,
    )


def _owner_safe_matrix() -> CapabilityPermissionMatrix:
    return CapabilityPermissionMatrix(
        memory_explicit_write=ActionPermission.ALLOW,
        memory_auto_write=ActionPermission.ASK,
        profile_write=ActionPermission.ASK,
        auto_fetch=ActionPermission.ASK,
        live_oauth_sync=ActionPermission.ASK,
        connectors_oauth=ActionPermission.ASK,
        mcp_execute=ActionPermission.ASK,
        mcp_install_launch=ActionPermission.ASK,
        skills_update_create=ActionPermission.ASK,
        provider_retry_fallback=ActionPermission.ASK,
        learning_mutation_candidates=ActionPermission.ASK,
        file_write=ActionPermission.ASK,
        file_delete=ActionPermission.ASK,
        browser_click_type=ActionPermission.ASK,
        computer_actions=ActionPermission.ASK,
        external_upload_send=ActionPermission.ASK,
        shell_command_execution=ActionPermission.ASK,
    )
