from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REDACTED = "[REDACTED]"
_REF_ID_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_UNSAFE_KEY_PARTS = ("authorization", "bearer", "password", "prompt", "raw", "secret", "token", "transcript")


class CapabilityRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CapabilityKind(str, Enum):
    TOOL = "tool"
    MCP_SERVER = "mcp_server"
    MCP_TOOL = "mcp_tool"
    SKILL = "skill"
    PLUGIN = "plugin"
    CONNECTOR = "connector"
    INTEGRATION = "integration"
    HARNESS = "harness"
    PLANNER = "planner"
    VERIFIER = "verifier"


class ToolRiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolSideEffectLevel(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    WRITE_LOCAL = "write_local"
    NETWORK = "network"
    BROWSER_ACTION = "browser_action"
    DESKTOP_ACTION = "desktop_action"
    CREDENTIAL_ACTION = "credential_action"
    PURCHASE_OR_PAYMENT = "purchase_or_payment"
    DESTRUCTIVE = "destructive"


class CapabilityExecutionMode(str, Enum):
    PROPOSAL_ONLY = "proposal_only"
    DRY_RUN = "dry_run"
    REQUIRES_APPROVAL = "requires_approval"
    APPROVED_EXECUTE = "approved_execute"
    DENIED = "denied"


class CapabilityStopReason(str, Enum):
    NOT_STOPPED = "not_stopped"
    MAX_STEPS_REACHED = "max_steps_reached"
    POLICY_DENIED = "policy_denied"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    REPEATED_FAILURES = "repeated_failures"
    DRY_RUN_COMPLETE = "dry_run_complete"
    PROPOSAL_ONLY_COMPLETE = "proposal_only_complete"
    VERIFICATION_FAILED = "verification_failed"
    COMPLETED = "completed"


class CapabilityRef(CapabilityRuntimeModel):
    kind: CapabilityKind
    identifier: str = Field(..., min_length=1)

    @field_validator("identifier")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        return _validate_safe_id(value, label="capability identifier")

    def safe_projection(self) -> dict[str, str]:
        return {"kind": self.kind.value, "identifier": self.identifier}


class CapabilityManifest(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    display_name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    owner_package: str = Field(..., min_length=1)
    adapter_boundary: str = Field(..., min_length=1)
    permissions: tuple[str, ...] = ()
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enabled_by_default: Literal[False] = False

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_safe_id(value, label="permission") for value in values)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "capability_ref": self.capability_ref.safe_projection(),
            "display_name": self.display_name,
            "owner_package": self.owner_package,
            "adapter_boundary": self.adapter_boundary,
            "permission_count": len(self.permissions),
            "input_schema_present": self.input_schema is not None,
            "output_schema_present": self.output_schema is not None,
            "metadata_keys": safe_metadata_keys(self.metadata),
        }


class HumanApprovalRequirement(CapabilityRuntimeModel):
    required: bool
    reason_code: str = Field(..., min_length=1)
    prompt_user_visible: bool
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.NONE

    @field_validator("reason_code")
    @classmethod
    def _validate_reason_code(cls, value: str) -> str:
        return _validate_safe_id(value, label="human approval reason_code")


class CapabilityPermissionDecision(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    decision: Literal["approved", "denied", "requires_human_approval"]
    reason_code: str = Field(..., min_length=1)
    human_approval: HumanApprovalRequirement

    @model_validator(mode="after")
    def _validate_human_approval_decision(self) -> CapabilityPermissionDecision:
        if self.decision == "requires_human_approval" and not self.human_approval.required:
            raise ValueError("requires_human_approval decisions must include human approval requirement")
        return self

    @field_validator("decision_id", "reason_code")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_safe_id(value, label="permission decision field")


class CapabilityEligibilityDecision(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    capability_ref: CapabilityRef
    eligible: bool
    reason_code: str = Field(..., min_length=1)
    intent_tags: tuple[str, ...] = ()

    @field_validator("decision_id", "reason_code")
    @classmethod
    def _validate_fields(cls, value: str) -> str:
        return _validate_safe_id(value, label="eligibility field")

    def safe_projection(self) -> dict[str, object]:
        return {
            "identifier": self.capability_ref.identifier,
            "kind": self.capability_ref.kind.value,
            "eligible": self.eligible,
            "reason_code": self.reason_code,
            "intent_tags": list(self.intent_tags),
        }


def _validate_safe_id(value: str, *, label: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be non-empty and trimmed")
    if any(character not in _REF_ID_SAFE_CHARS for character in value):
        raise ValueError(f"{label} must contain only safe id characters")
    return value


def safe_metadata_keys(metadata: dict[str, Any]) -> list[str]:
    return sorted(REDACTED if _unsafe_key(str(key)) else str(key) for key in metadata)


def _unsafe_key(value: str) -> bool:
    normalized = "".join(character for character in value.lower() if character.isalnum())
    return any(part in normalized for part in _UNSAFE_KEY_PARTS)
