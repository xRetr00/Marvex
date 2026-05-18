from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.context_runtime import ContextCandidate, ContextPack, ContextSourceKind, ContextSourceRef
from packages.intent_runtime import IntentKind, IntentRef

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class PromptSectionKind(str, Enum):
    SYSTEM_POLICY = "system_policy"
    USER_CONTEXT = "user_context"
    CAPABILITY_SCHEMA = "capability_schema"
    MEMORY_CONTEXT = "memory_context"
    SKILL_CONTRIBUTION = "skill_contribution"
    TOOL_RESULT = "tool_result"
    APPROVAL_STATE = "approval_state"
    RESPONSE_CONTRACT = "response_contract"


class ContextOverflowStrategy(str, Enum):
    KEEP = "keep"
    EXCLUDE = "exclude"
    COMPACT_SAFE_SUMMARY = "compact_safe_summary"
    OFFLOAD_BY_REF = "offload_by_ref"


class ContextRetentionReason(str, Enum):
    CURRENT_USER_INTENT = "current_user_intent"
    ELIGIBLE_CAPABILITY_SCHEMA = "eligible_capability_schema"
    SELECTED_MEMORY = "selected_memory"
    TOOL_RESULT_SUMMARY = "tool_result_summary"
    SAFETY_APPROVAL_STATE = "safety_approval_state"


class PromptBudgetReport(CapabilityRuntimeModel):
    max_context_tokens: int = Field(..., ge=0)
    used_context_tokens: int = Field(..., ge=0)
    section_count: int = Field(..., ge=0)
    within_budget: bool


class PromptSection(CapabilityRuntimeModel):
    kind: PromptSectionKind
    source_ref: ContextSourceRef
    safe_content: str = Field(..., min_length=1, max_length=1600)
    token_estimate: int = Field(..., ge=0)
    included: bool
    reason_code: str = Field(..., min_length=1)
    raw_content_persisted: Literal[False] = False

    @field_validator("reason_code")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _safe_id(value, "prompt section reason_code")

    @field_validator("safe_content")
    @classmethod
    def _reject_raw_content(cls, value: str) -> str:
        lowered = value.lower()
        if any(marker in lowered for marker in ("authorization:", "bearer ", "api_key", "password", "raw transcript", "raw prompt")):
            raise ValueError("prompt sections must use safe projections")
        return value


class PromptHarnessPlan(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent_ref: IntentRef
    sections: tuple[PromptSection, ...]
    all_tools_included: Literal[False] = False
    all_memory_included: Literal[False] = False
    raw_prompt_persisted: Literal[False] = False


class PromptAssemblyRequest(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent_ref: IntentRef
    context_pack: ContextPack


class SafePromptProjection(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent: dict[str, str]
    section_count: int
    section_kinds: tuple[str, ...]
    budget_report: dict[str, int | bool]
    raw_prompt_persisted: Literal[False] = False


class PromptAssemblyResult(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    plan: PromptHarnessPlan
    budget_report: PromptBudgetReport
    raw_prompt_persisted: Literal[False] = False

    def safe_projection(self) -> SafePromptProjection:
        return SafePromptProjection(
            schema_version=self.schema_version,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            intent=self.plan.intent_ref.safe_projection(),
            section_count=len(self.plan.sections),
            section_kinds=tuple(section.kind.value for section in self.plan.sections),
            budget_report={
                "max_context_tokens": self.budget_report.max_context_tokens,
                "used_context_tokens": self.budget_report.used_context_tokens,
                "section_count": self.budget_report.section_count,
                "within_budget": self.budget_report.within_budget,
            },
        )


def assemble_prompt_harness(request: PromptAssemblyRequest) -> PromptAssemblyResult:
    if request.context_pack.all_context_injected:
        raise ValueError("prompt harness forbids all-context injection")
    sections = [_system_policy_section(request.intent_ref)]
    sections.extend(_section_from_candidate(candidate) for candidate in request.context_pack.included)
    sections.append(_response_contract_section(request.intent_ref))
    budget = PromptBudgetReport(
        max_context_tokens=request.context_pack.budget.max_context_tokens,
        used_context_tokens=sum(section.token_estimate for section in sections if section.included),
        section_count=len(sections),
        within_budget=sum(section.token_estimate for section in sections if section.included) <= request.context_pack.budget.max_context_tokens,
    )
    return PromptAssemblyResult(
        schema_version=request.schema_version,
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        plan=PromptHarnessPlan(schema_version=request.schema_version, trace_id=request.trace_id, turn_id=request.turn_id, intent_ref=request.intent_ref, sections=tuple(sections)),
        budget_report=budget,
    )


def _system_policy_section(intent_ref: IntentRef) -> PromptSection:
    return PromptSection(kind=PromptSectionKind.SYSTEM_POLICY, source_ref=ContextSourceRef(kind=ContextSourceKind.TRACE_TELEMETRY_SUMMARY, identifier="marvex.policy"), safe_content=f"Marvex policy remains authoritative. Intent: {intent_ref.intent_kind.value}.", token_estimate=10, included=True, reason_code="section.system_policy")


def _response_contract_section(intent_ref: IntentRef) -> PromptSection:
    content = "Ask one clarification question." if intent_ref.intent_kind == IntentKind.CLARIFICATION else "Continue with only included safe context sections."
    return PromptSection(kind=PromptSectionKind.RESPONSE_CONTRACT, source_ref=ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier="response.contract"), safe_content=content, token_estimate=8, included=True, reason_code="section.response_contract")


def _section_from_candidate(candidate: ContextCandidate) -> PromptSection:
    mapping = {
        ContextSourceKind.CAPABILITY_SCHEMA: PromptSectionKind.CAPABILITY_SCHEMA,
        ContextSourceKind.MCP_TOOL_SCHEMA: PromptSectionKind.CAPABILITY_SCHEMA,
        ContextSourceKind.MEMORY_PROJECTION: PromptSectionKind.MEMORY_CONTEXT,
        ContextSourceKind.SKILL_PROMPT_CONTRIBUTION: PromptSectionKind.SKILL_CONTRIBUTION,
        ContextSourceKind.TOOL_RESULT: PromptSectionKind.TOOL_RESULT,
    }
    kind = mapping.get(candidate.source_ref.kind, PromptSectionKind.USER_CONTEXT)
    return PromptSection(kind=kind, source_ref=candidate.source_ref, safe_content=candidate.safe_summary, token_estimate=candidate.token_estimate, included=True, reason_code="section.safe_context_candidate")


class CompactionCandidate(CapabilityRuntimeModel):
    source_ref: ContextSourceRef
    token_estimate: int = Field(..., ge=0)
    retention_reason: str = Field(..., min_length=1)
    safe_summary: str = Field(..., min_length=1, max_length=1200)
    raw_content_persisted: Literal[False] = False


class SafeCompactionProjection(CapabilityRuntimeModel):
    source_ref: dict[str, str]
    strategy: ContextOverflowStrategy
    retention_reason: str
    raw_content_persisted: Literal[False] = False


class CompactionDecision(CapabilityRuntimeModel):
    source_ref: ContextSourceRef
    strategy: ContextOverflowStrategy
    retention_reason: str
    offload_ref: str | None = None
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> SafeCompactionProjection:
        return SafeCompactionProjection(source_ref=self.source_ref.safe_projection(), strategy=self.strategy, retention_reason=self.retention_reason)


class ToolResultClearingDecision(CapabilityRuntimeModel):
    source_ref: ContextSourceRef
    clear_from_prompt: bool
    reason_code: str
    raw_tool_result_persisted: Literal[False] = False

    @classmethod
    def from_candidate(cls, candidate: CompactionCandidate) -> "ToolResultClearingDecision":
        return cls(source_ref=candidate.source_ref, clear_from_prompt=candidate.source_ref.kind == ContextSourceKind.TOOL_RESULT, reason_code="tool_result.clear_after_summary")


class MemoryOffloadDecision(CapabilityRuntimeModel):
    source_ref: ContextSourceRef
    offload_allowed: bool
    reason_code: str
    raw_memory_persisted: Literal[False] = False


def decide_compaction(candidate: CompactionCandidate, *, max_tokens: int) -> CompactionDecision:
    if candidate.token_estimate <= max_tokens:
        strategy = ContextOverflowStrategy.KEEP
        offload_ref = None
    elif candidate.source_ref.kind == ContextSourceKind.TOOL_RESULT:
        strategy = ContextOverflowStrategy.OFFLOAD_BY_REF
        offload_ref = f"local://context-offload/{candidate.source_ref.identifier}"
    else:
        strategy = ContextOverflowStrategy.COMPACT_SAFE_SUMMARY
        offload_ref = None
    return CompactionDecision(source_ref=candidate.source_ref, strategy=strategy, retention_reason=candidate.retention_reason, offload_ref=offload_ref)


class PlanningNeedDecision(CapabilityRuntimeModel):
    intent_ref: IntentRef
    planning_needed: bool
    reason_code: str
    autonomous_loop_started: Literal[False] = False

    @classmethod
    def from_intent(cls, intent_ref: IntentRef, *, context_candidate_count: int) -> "PlanningNeedDecision":
        needed = intent_ref.intent_kind in {IntentKind.CAPABILITY_TOOL, IntentKind.BROWSER_COMPUTER_USE, IntentKind.MCP_SKILL} or context_candidate_count > 2
        return cls(intent_ref=intent_ref, planning_needed=needed, reason_code="planning.context_or_capability_needed" if needed else "planning.not_needed")


class TaskDecompositionHint(CapabilityRuntimeModel):
    hint_id: str
    plan_context_requirements: tuple[str, ...]
    recursive_agent_loop_allowed: Literal[False] = False


class PlanContextRequirement(CapabilityRuntimeModel):
    requirement_id: str
    source_kind: ContextSourceKind
    required: bool


class VerificationNeedDecision(CapabilityRuntimeModel):
    verification_needed: bool
    reason_code: str
    autonomous_verifier_started: Literal[False] = False


class HarnessValidationResult(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    valid: bool
    reason_codes: tuple[str, ...]
    validator_backend: str
    prompt_section_count: int = Field(..., ge=0)
    auto_retry_started: Literal[False] = False
    raw_prompt_persisted: Literal[False] = False

    @classmethod
    def validated(cls, *, schema_version: str, trace_id: str, turn_id: str, prompt_section_count: int, validator_backend: str = "marvex_models") -> "HarnessValidationResult":
        return cls(schema_version=schema_version, trace_id=trace_id, turn_id=turn_id, valid=True, reason_codes=("validated",), validator_backend=validator_backend, prompt_section_count=prompt_section_count)


class HarnessTelemetrySummary(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    selected_intent: str
    route_confidence_bucket: str
    context_candidates_count: int
    included_context_count: int
    excluded_context_count: int
    prompt_section_count: int
    context_budget_status: str
    compaction_strategy: str | None = None
    selected_capability_schema_count: int
    planning_needed: bool
    raw_prompt_persisted: Literal[False] = False
    raw_context_persisted: Literal[False] = False

    @classmethod
    def from_harness(cls, result: PromptAssemblyResult, *, route_confidence_bucket: str, context_candidates_count: int, excluded_context_count: int, planning_needed: bool, compaction_strategy: str | None = None) -> "HarnessTelemetrySummary":
        capability_count = sum(1 for section in result.plan.sections if section.kind == PromptSectionKind.CAPABILITY_SCHEMA)
        return cls(schema_version=result.schema_version, trace_id=result.trace_id, turn_id=result.turn_id, selected_intent=result.plan.intent_ref.intent_kind.value, route_confidence_bucket=route_confidence_bucket, context_candidates_count=context_candidates_count, included_context_count=len(result.plan.sections), excluded_context_count=excluded_context_count, prompt_section_count=len(result.plan.sections), context_budget_status="within_budget" if result.budget_report.within_budget else "over_budget", compaction_strategy=compaction_strategy, selected_capability_schema_count=capability_count, planning_needed=planning_needed)


def _safe_id(value: str, label: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be non-empty and trimmed")
    if any(character not in _SAFE_ID_CHARS for character in value):
        raise ValueError(f"{label} must contain only safe id characters")
    return value
