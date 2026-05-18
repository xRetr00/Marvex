from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.capability_runtime import (
    ApprovalDecision,
    CapabilityApprovalRequest,
    CapabilityExecutionMode,
    CapabilityRef,
    PendingApprovalState,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


SCHEMA_VERSION = "1"
UNSAFE_TEXT_PARTS = ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")


class ControlPlaneModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ApprovalSummary(ControlPlaneModel):
    schema_version: str = Field(..., min_length=1)
    approval_request_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    capability_summary: dict[str, str]
    user_visible_summary: str = Field(..., min_length=1, max_length=500)
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    execution_mode: CapabilityExecutionMode = CapabilityExecutionMode.REQUIRES_APPROVAL
    status: Literal["pending"] = "pending"
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def from_request(cls, request: CapabilityApprovalRequest) -> ApprovalSummary:
        pending = PendingApprovalState.from_request(request)
        return cls(
            schema_version=request.schema_version,
            approval_request_id=request.approval_request_id,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            capability_summary=_capability_summary(request.capability_ref),
            user_visible_summary=request.prompt.user_visible_summary,
            risk_level=pending.risk_level,
            side_effect_level=pending.side_effect_level,
        )


class ApprovalListResponse(ControlPlaneModel):
    schema_version: str = Field(..., min_length=1)
    approvals: tuple[ApprovalSummary, ...]
    pending_count: int = Field(..., ge=0)
    raw_payload_persisted: Literal[False] = False


class ApprovalDecisionInput(ControlPlaneModel):
    reason: str = Field(..., min_length=1, max_length=300)

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("approval reason must be trimmed")
        return _safe_text(value)


class ApprovalDecisionResponse(ControlPlaneModel):
    schema_version: str = Field(..., min_length=1)
    approval_request_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    capability_summary: dict[str, str]
    decision: Literal["approved", "denied"]
    reason: str = Field(..., min_length=1, max_length=300)
    execution_started: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def from_decision(
        cls,
        *,
        request: CapabilityApprovalRequest,
        decision: ApprovalDecision,
        reason: str,
    ) -> ApprovalDecisionResponse:
        return cls(
            schema_version=request.schema_version,
            approval_request_id=request.approval_request_id,
            decision_id=decision.decision_id,
            capability_summary=_capability_summary(request.capability_ref),
            decision=decision.decision,
            reason=reason,
        )



class ApprovalHistoryResponse(ControlPlaneModel):
    schema_version: str = Field(..., min_length=1)
    decisions: tuple[ApprovalDecisionResponse, ...]
    decision_count: int = Field(..., ge=0)
    raw_payload_persisted: Literal[False] = False
class ProviderStatusView(ControlPlaneModel):
    provider_id: str = Field(..., min_length=1)
    configured: bool
    secret_present: bool = False
    secret_value_present: Literal[False] = False


class ControlPlaneSnapshot(ControlPlaneModel):
    schema_version: str = Field(..., min_length=1)
    providers: tuple[dict[str, Any], ...] = ()
    capabilities: tuple[dict[str, Any], ...] = ()
    tools: tuple[dict[str, Any], ...] = ()
    mcp_servers: tuple[dict[str, Any], ...] = ()
    skills: tuple[dict[str, Any], ...] = ()
    traces: tuple[dict[str, Any], ...] = ()
    memory: tuple[dict[str, Any], ...] = ()
    sessions: tuple[dict[str, Any], ...] = ()
    agent_loops: tuple[dict[str, Any], ...] = ()
    telemetry: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, bool] = Field(default_factory=dict)
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def foundation_default(
        cls,
        *,
        schema_version: str,
        providers: tuple[dict[str, Any], ...] = (),
        capabilities: tuple[dict[str, Any], ...] = (),
        tools: tuple[dict[str, Any], ...] = (),
        mcp_servers: tuple[dict[str, Any], ...] = (),
        skills: tuple[dict[str, Any], ...] = (),
        traces: tuple[dict[str, Any], ...] = (),
        memory: tuple[dict[str, Any], ...] = (),
        sessions: tuple[dict[str, Any], ...] = (),
        agent_loops: tuple[dict[str, Any], ...] = (),
        telemetry: dict[str, Any] | None = None,
        settings: dict[str, bool] | None = None,
    ) -> ControlPlaneSnapshot:
        return cls(
            schema_version=schema_version,
            providers=tuple(_provider_view(provider).model_dump() for provider in providers),
            capabilities=tuple(_safe_mapping(item) for item in capabilities),
            tools=tuple(_safe_mapping(item) for item in tools),
            mcp_servers=tuple(_safe_mapping(item) for item in mcp_servers),
            skills=tuple(_safe_mapping(item) for item in skills),
            traces=tuple(_safe_mapping(item) for item in traces),
            memory=tuple(_safe_mapping(item) for item in memory),
            sessions=tuple(_safe_mapping(item) for item in sessions),
            agent_loops=tuple(_safe_mapping(item) for item in agent_loops),
            telemetry=_safe_mapping(telemetry or {}),
            settings=dict(settings or {}),
        )


def _capability_summary(ref: CapabilityRef) -> dict[str, str]:
    return {"kind": ref.kind.value, "identifier": ref.identifier}


def _provider_view(value: dict[str, Any]) -> ProviderStatusView:
    return ProviderStatusView(
        provider_id=str(value.get("provider_id", "unknown")),
        configured=bool(value.get("configured", False)),
        secret_present=bool(value.get("secret_present", False)),
    )


def _safe_mapping(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if _unsafe_key(key_text):
            continue
        if isinstance(item, str):
            safe[key_text] = _safe_text(item)
        elif isinstance(item, int | float | bool) or item is None:
            safe[key_text] = item
    return safe


def _safe_text(value: str) -> str:
    lowered = value.lower()
    if any(part in lowered for part in UNSAFE_TEXT_PARTS):
        return "[redacted]"
    return value


def _unsafe_key(value: str) -> bool:
    lowered = value.lower().replace("-", "_")
    return any(part in lowered for part in UNSAFE_TEXT_PARTS) or lowered.startswith("raw_")
