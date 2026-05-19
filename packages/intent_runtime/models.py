from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from packages.capability_runtime.models import CapabilityRuntimeModel, ToolRiskLevel

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class IntentKind(str, Enum):
    CAPABILITY_TOOL = "capability_tool"
    WEB_SEARCH = "web_search"
    GROUNDED_ANSWER = "grounded_answer"
    MEMORY = "memory"
    MEMORY_TREE_NEEDED = "memory_tree_needed"
    PROVIDER_SIMPLE_CHAT = "provider_simple_chat"
    BROWSER_COMPUTER_USE = "browser_computer_use"
    MCP_SKILL = "mcp_skill"
    MCP_NEEDED = "mcp_needed"
    SKILL_NEEDED = "skill_needed"
    SETTINGS_CONTROL_PLANE = "settings_control_plane"
    CONNECTOR_ACCOUNT = "connector_account"
    FILE_READ_LIST_SEARCH = "file_read_list_search"
    RISKY_ACTION = "risky_action"
    CLARIFICATION = "clarification"
    UNSAFE_OR_INJECTION_SUSPECTED = "unsafe_or_injection_suspected"
    UNSAFE_RISKY = "unsafe_risky"


class IntentConfidenceBucket(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentRiskSignal(str, Enum):
    NONE = "none"
    RISKY_ACTION_REQUESTED = "risky_action_requested"
    UNSAFE_REQUEST = "unsafe_request"


class ClarificationNeededDecision(str, Enum):
    NOT_NEEDED = "not_needed"
    NEEDED = "needed"


class IntentRef(CapabilityRuntimeModel):
    intent_id: str = Field(..., min_length=1)
    intent_kind: IntentKind

    @field_validator("intent_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return _safe_id(value, "intent_id")

    def safe_projection(self) -> dict[str, str]:
        return {"intent_id": self.intent_id, "intent_kind": self.intent_kind.value}


class IntentConfidence(CapabilityRuntimeModel):
    score: float = Field(..., ge=0.0, le=1.0)
    bucket: IntentConfidenceBucket

    @classmethod
    def from_score(cls, score: float) -> "IntentConfidence":
        if score >= 0.75:
            bucket = IntentConfidenceBucket.HIGH
        elif score >= 0.45:
            bucket = IntentConfidenceBucket.MEDIUM
        else:
            bucket = IntentConfidenceBucket.LOW
        return cls(score=score, bucket=bucket)


class IntentAmbiguitySignal(CapabilityRuntimeModel):
    ambiguous: bool
    reason_code: str = Field(..., min_length=1)
    candidate_count: int = Field(..., ge=0)

    @field_validator("reason_code")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _safe_id(value, "ambiguity reason_code")


class IntentCandidate(CapabilityRuntimeModel):
    intent_ref: IntentRef
    confidence: IntentConfidence
    reason_code: str = Field(..., min_length=1)
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE

    @property
    def intent_kind(self) -> IntentKind:
        return self.intent_ref.intent_kind

    @field_validator("reason_code")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _safe_id(value, "candidate reason_code")


class IntentClassificationRequest(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    user_input_summary: str = Field(..., min_length=1, max_length=600)
    raw_input_persisted: Literal[False] = False


class IntentRouteDecision(CapabilityRuntimeModel):
    route_id: str = Field(..., min_length=1)
    selected_intent_ref: IntentRef
    policy_owner: Literal["packages.capability_runtime"] = "packages.capability_runtime"
    execution_allowed: Literal[False] = False
    reason_code: str = Field(..., min_length=1)

    @field_validator("route_id", "reason_code")
    @classmethod
    def _validate_fields(cls, value: str) -> str:
        return _safe_id(value, "route decision field")


class SafeIntentProjection(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    selected_intent: dict[str, str]
    confidence_bucket: IntentConfidenceBucket
    risk_signal: IntentRiskSignal
    clarification_needed: ClarificationNeededDecision
    route_reason_code: str
    raw_input_persisted: Literal[False] = False


class IntentClassificationResult(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    candidates: tuple[IntentCandidate, ...]
    selected_intent: IntentRef
    confidence: IntentConfidence
    route_decision: IntentRouteDecision
    risk_signal: IntentRiskSignal = IntentRiskSignal.NONE
    ambiguity_signal: IntentAmbiguitySignal
    clarification: ClarificationNeededDecision
    backend_name: str = "deterministic"
    library_owns_policy: Literal[False] = False
    hybrid_details: dict[str, object] = Field(default_factory=dict)
    raw_input_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _selected_must_be_candidate(self) -> "IntentClassificationResult":
        if self.selected_intent not in tuple(candidate.intent_ref for candidate in self.candidates):
            raise ValueError("selected intent must be one of the candidates")
        return self

    def safe_projection(self) -> SafeIntentProjection:
        return SafeIntentProjection(
            schema_version=self.schema_version,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            selected_intent=self.selected_intent.safe_projection(),
            confidence_bucket=self.confidence.bucket,
            risk_signal=self.risk_signal,
            clarification_needed=self.clarification,
            route_reason_code=self.route_decision.reason_code,
        )


def classify_intent(request: IntentClassificationRequest) -> IntentClassificationResult:
    try:
        from packages.intent_runtime.hybrid import HybridIntentRuntime

        return HybridIntentRuntime.default().classify(request)
    except Exception:
        text = request.user_input_summary.lower()
        if any(marker in text for marker in ("delete all", "steal", "bypass", "credential", "password")):
            kind = IntentKind.UNSAFE_OR_INJECTION_SUSPECTED
            score = 0.88
            risk = IntentRiskSignal.UNSAFE_REQUEST
            risk_level = ToolRiskLevel.CRITICAL
        elif any(marker in text for marker in ("click", "browser", "checkout", "computer", "desktop")):
            kind = IntentKind.BROWSER_COMPUTER_USE
            score = 0.82
            risk = IntentRiskSignal.RISKY_ACTION_REQUESTED
            risk_level = ToolRiskLevel.HIGH
        elif any(marker in text for marker in ("memory tree", "source grounded", "evidence")):
            kind = IntentKind.MEMORY_TREE_NEEDED
            score = 0.83
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.LOW
        elif any(marker in text for marker in ("remember", "memory", "preference")):
            kind = IntentKind.MEMORY
            score = 0.81
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.LOW
        elif any(marker in text for marker in ("control plane", "settings", "approval", "telemetry")):
            kind = IntentKind.SETTINGS_CONTROL_PLANE
            score = 0.8
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.LOW
        elif any(marker in text for marker in ("mcp", "server tool")):
            kind = IntentKind.MCP_NEEDED
            score = 0.82
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.LOW
        elif any(marker in text for marker in ("skill", "skill package")):
            kind = IntentKind.SKILL_NEEDED
            score = 0.8
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.LOW
        elif any(marker in text for marker in ("tool", "calculator", "capability")):
            kind = IntentKind.CAPABILITY_TOOL
            score = 0.84
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.LOW
        elif any(marker in text for marker in ("that thing", "before", "it")):
            kind = IntentKind.CLARIFICATION
            score = 0.32
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.SAFE
        else:
            kind = IntentKind.PROVIDER_SIMPLE_CHAT
            score = 0.7
            risk = IntentRiskSignal.NONE
            risk_level = ToolRiskLevel.SAFE
        return classification_from_kind(request, kind=kind, score=score, risk_signal=risk, risk_level=risk_level, reason_code="intent.deterministic_foundation")

def classification_from_kind(
    request: IntentClassificationRequest,
    *,
    kind: IntentKind,
    score: float,
    risk_signal: IntentRiskSignal = IntentRiskSignal.NONE,
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE,
    reason_code: str = "intent.adapter_route",
    backend_name: str = "deterministic",
    hybrid_details: dict[str, object] | None = None,
) -> IntentClassificationResult:
    confidence = IntentConfidence.from_score(score)
    if confidence.bucket == IntentConfidenceBucket.LOW:
        kind = IntentKind.CLARIFICATION
    intent_ref = IntentRef(intent_id=f"intent.{kind.value}", intent_kind=kind)
    candidate = IntentCandidate(intent_ref=intent_ref, confidence=confidence, reason_code=reason_code, risk_level=risk_level)
    clarification = ClarificationNeededDecision.NEEDED if kind == IntentKind.CLARIFICATION or confidence.bucket == IntentConfidenceBucket.LOW else ClarificationNeededDecision.NOT_NEEDED
    ambiguous = clarification == ClarificationNeededDecision.NEEDED
    return IntentClassificationResult(
        schema_version=request.schema_version,
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        candidates=(candidate,),
        selected_intent=intent_ref,
        confidence=confidence,
        route_decision=IntentRouteDecision(route_id=f"route.{kind.value}", selected_intent_ref=intent_ref, reason_code=reason_code),
        risk_signal=risk_signal,
        ambiguity_signal=IntentAmbiguitySignal(ambiguous=ambiguous, reason_code="intent.low_confidence" if ambiguous else "intent.clear", candidate_count=1),
        clarification=clarification,
        backend_name=backend_name,
        hybrid_details=hybrid_details or {},
    )


def _safe_id(value: str, label: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be non-empty and trimmed")
    if any(character not in _SAFE_ID_CHARS for character in value):
        raise ValueError(f"{label} must contain only safe id characters")
    return value
