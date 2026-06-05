from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from packages.capability_runtime import CapabilityEligibilityDecision, CapabilityKind
from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.intent_runtime import IntentKind, IntentRef

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_MAX_CONTEXT_TOKENS = 2_000_000


class ContextSourceKind(str, Enum):
    SESSION_REF = "session_ref"
    CONVERSATION_REF = "conversation_ref"
    MEMORY_PROJECTION = "memory_projection"
    CAPABILITY_SCHEMA = "capability_schema"
    SKILL_PROMPT_CONTRIBUTION = "skill_prompt_contribution"
    MCP_TOOL_SCHEMA = "mcp_tool_schema"
    TRACE_TELEMETRY_SUMMARY = "trace_telemetry_summary"
    PROVIDER_STATE = "provider_state"
    USER_INPUT_SUMMARY = "user_input_summary"
    TOOL_RESULT = "tool_result"
    WEB_SEARCH_EVIDENCE = "web_search_evidence"


class ContextSourceTrustLevel(str, Enum):
    INTERNAL_SAFE_PROJECTION = "internal_safe_projection"
    USER_SUMMARY = "user_summary"
    UNTRUSTED_SUMMARY = "untrusted_summary"


class ContextExclusionReason(str, Enum):
    NOT_EXCLUDED = "not_excluded"
    SOURCE_KIND_NOT_ALLOWED = "excluded.source_kind_not_allowed"
    INTENT_MISMATCH = "excluded.intent_mismatch"
    BUDGET_EXCEEDED = "excluded.budget_exceeded"
    MAX_CANDIDATES_REACHED = "excluded.max_candidates_reached"
    UNSAFE_RAW_CONTENT = "excluded.unsafe_raw_content"


class ContextSourceRef(CapabilityRuntimeModel):
    kind: ContextSourceKind
    identifier: str = Field(..., min_length=1)

    @field_validator("identifier")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        return _safe_id(value, "context source identifier")

    def safe_projection(self) -> dict[str, str]:
        return {"kind": self.kind.value, "identifier": self.identifier}


class ContextBudget(CapabilityRuntimeModel):
    max_context_tokens: int = Field(..., ge=0, le=_MAX_CONTEXT_TOKENS)
    reserved_response_tokens: int = Field(..., ge=0, le=200_000)


class ContextDeliveryPolicy(CapabilityRuntimeModel):
    max_candidates: int = Field(..., ge=0, le=100)
    allowed_source_kinds: tuple[ContextSourceKind, ...] = (ContextSourceKind.USER_INPUT_SUMMARY, ContextSourceKind.CAPABILITY_SCHEMA, ContextSourceKind.MCP_TOOL_SCHEMA, ContextSourceKind.MEMORY_PROJECTION, ContextSourceKind.SKILL_PROMPT_CONTRIBUTION, ContextSourceKind.TOOL_RESULT, ContextSourceKind.WEB_SEARCH_EVIDENCE)
    include_excluded_reasons: bool = False
    browser_computer_default_excluded: bool = True
    all_tools_allowed: Literal[False] = False
    all_memory_allowed: Literal[False] = False
    raw_transcripts_allowed: Literal[False] = False


class ContextCandidate(CapabilityRuntimeModel):
    source_ref: ContextSourceRef
    safe_summary: str = Field(..., min_length=1, max_length=1200)
    token_estimate: int = Field(..., ge=0, le=_MAX_CONTEXT_TOKENS)
    intent_tags: tuple[str, ...] = ()
    trust_level: ContextSourceTrustLevel = ContextSourceTrustLevel.INTERNAL_SAFE_PROJECTION
    raw_content_persisted: Literal[False] = False

    @classmethod
    def from_safe_summary(
        cls,
        source_ref: ContextSourceRef,
        safe_summary: str,
        *,
        token_estimate: int,
        intent_tags: tuple[str, ...] = (),
        trust_level: ContextSourceTrustLevel = ContextSourceTrustLevel.INTERNAL_SAFE_PROJECTION,
    ) -> "ContextCandidate":
        return cls(source_ref=source_ref, safe_summary=safe_summary, token_estimate=token_estimate, intent_tags=intent_tags, trust_level=trust_level)

    @classmethod
    def from_capability_schema(
        cls,
        decision: CapabilityEligibilityDecision,
        *,
        token_estimate: int,
        trust_level: ContextSourceTrustLevel = ContextSourceTrustLevel.INTERNAL_SAFE_PROJECTION,
    ) -> "ContextCandidate":
        kind = ContextSourceKind.MCP_TOOL_SCHEMA if decision.capability_ref.kind == CapabilityKind.MCP_TOOL else ContextSourceKind.CAPABILITY_SCHEMA
        return cls(
            source_ref=ContextSourceRef(kind=kind, identifier=decision.capability_ref.identifier),
            safe_summary=f"{decision.capability_ref.kind.value}:{decision.capability_ref.identifier}:{decision.reason_code}",
            token_estimate=token_estimate,
            intent_tags=decision.intent_tags,
            trust_level=trust_level,
        )

    @field_validator("safe_summary")
    @classmethod
    def _reject_unsafe_summary(cls, value: str) -> str:
        lowered = value.lower()
        if any(marker in lowered for marker in ("authorization:", "bearer ", "api_key", "password", "raw transcript", "raw prompt")):
            raise ValueError("context candidates must be safe projections")
        return value


class ContextEligibilityDecision(CapabilityRuntimeModel):
    source_ref: ContextSourceRef
    eligible: bool
    reason_code: str = Field(..., min_length=1)
    token_estimate: int = Field(..., ge=0)

    @field_validator("reason_code")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _safe_id(value, "context eligibility reason_code")


class SafeContextProjection(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent: dict[str, str]
    included_count: int
    excluded_count: int
    used_context_tokens: int
    max_context_tokens: int
    included_sources: tuple[dict[str, str], ...]
    excluded_sources: tuple[dict[str, str], ...] = ()
    all_context_injected: Literal[False] = False
    raw_context_persisted: Literal[False] = False


class ContextPack(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent_ref: IntentRef
    budget: ContextBudget
    included: tuple[ContextCandidate, ...]
    excluded: tuple[ContextEligibilityDecision, ...]
    used_context_tokens: int = Field(..., ge=0)
    all_context_injected: Literal[False] = False
    raw_context_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_budget(self) -> "ContextPack":
        if self.used_context_tokens > self.budget.max_context_tokens:
            raise ValueError("context pack exceeds budget")
        return self

    def safe_projection(self) -> SafeContextProjection:
        return SafeContextProjection(
            schema_version=self.schema_version,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            intent=self.intent_ref.safe_projection(),
            included_count=len(self.included),
            excluded_count=len(self.excluded),
            used_context_tokens=self.used_context_tokens,
            max_context_tokens=self.budget.max_context_tokens,
            included_sources=tuple(item.source_ref.safe_projection() for item in self.included),
            excluded_sources=tuple(item.source_ref.safe_projection() for item in self.excluded),
        )


def build_context_pack(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    intent_ref: IntentRef,
    candidates: tuple[ContextCandidate, ...],
    budget: ContextBudget,
    policy: ContextDeliveryPolicy,
) -> ContextPack:
    included: list[ContextCandidate] = []
    excluded: list[ContextEligibilityDecision] = []
    used_tokens = 0
    for candidate in candidates:
        reason = _exclusion_reason(candidate, intent_ref, policy, used_tokens, budget, len(included))
        if reason != ContextExclusionReason.NOT_EXCLUDED:
            excluded.append(ContextEligibilityDecision(source_ref=candidate.source_ref, eligible=False, reason_code=reason.value, token_estimate=candidate.token_estimate))
            continue
        included.append(candidate)
        used_tokens += candidate.token_estimate
    if not policy.include_excluded_reasons:
        excluded = []
    return ContextPack(schema_version=schema_version, trace_id=trace_id, turn_id=turn_id, intent_ref=intent_ref, budget=budget, included=tuple(included), excluded=tuple(excluded), used_context_tokens=used_tokens)


def _exclusion_reason(candidate: ContextCandidate, intent_ref: IntentRef, policy: ContextDeliveryPolicy, used_tokens: int, budget: ContextBudget, included_count: int) -> ContextExclusionReason:
    if candidate.source_ref.kind not in policy.allowed_source_kinds:
        return ContextExclusionReason.SOURCE_KIND_NOT_ALLOWED
    if included_count >= policy.max_candidates:
        return ContextExclusionReason.MAX_CANDIDATES_REACHED
    if policy.browser_computer_default_excluded and intent_ref.intent_kind != IntentKind.BROWSER_COMPUTER_USE and "browser_computer_use" in candidate.intent_tags:
        return ContextExclusionReason.INTENT_MISMATCH
    if candidate.intent_tags and intent_ref.intent_kind.value not in candidate.intent_tags:
        return ContextExclusionReason.INTENT_MISMATCH
    if used_tokens + candidate.token_estimate > budget.max_context_tokens:
        return ContextExclusionReason.BUDGET_EXCEEDED
    return ContextExclusionReason.NOT_EXCLUDED


def _safe_id(value: str, label: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be non-empty and trimmed")
    if any(character not in _SAFE_ID_CHARS for character in value):
        raise ValueError(f"{label} must contain only safe id characters")
    return value
