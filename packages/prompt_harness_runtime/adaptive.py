from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from packages.capability_runtime import CapabilityManifest, ToolRiskLevel
from packages.context_runtime import (
    ContextBudget,
    ContextCandidate,
    ContextDeliveryPolicy,
    ContextPack,
    ContextSourceKind,
    ContextSourceRef,
    ContextSourceTrustLevel,
    build_context_pack,
)
from packages.intent_runtime import IntentKind, IntentRef
from packages.prompt_harness_runtime.models import (
    PromptAssemblyRequest,
    PromptAssemblyResult,
    PromptBlockSuppression,
    PromptBudgetReport,
    PromptHarnessPlan,
    PromptRouteProfile,
    PromptSection,
    PromptSectionKind,
    _response_contract_section,
    _section_from_candidate,
    _system_policy_section,
)


class AdaptivePromptRoute(str, Enum):
    SIMPLE_CHAT = "simple_chat"
    GROUNDED_LOOKUP = "grounded_lookup"
    MEMORY_QUERY = "memory_query"
    TOOL_USE = "tool_use"
    BROWSER = "browser"
    MCP = "mcp"
    CLARIFICATION = "clarification"


class AdaptiveContextPolicy:
    def __init__(self, *, route: AdaptivePromptRoute, delivery_policy: ContextDeliveryPolicy, budget: ContextBudget, profile: PromptRouteProfile) -> None:
        self.route = route
        self.delivery_policy = delivery_policy
        self.budget = budget
        self.profile = profile

    def build_pack(
        self,
        *,
        schema_version: str,
        trace_id: str,
        turn_id: str,
        intent_ref: IntentRef,
        candidates: tuple[ContextCandidate, ...],
    ) -> ContextPack:
        eligible = tuple(candidate for candidate in candidates if not candidate.source_ref.identifier.startswith("ineligible."))
        return build_context_pack(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            intent_ref=intent_ref,
            candidates=eligible,
            budget=self.budget,
            policy=self.delivery_policy,
        )


def adaptive_context_policy_for_route(route: AdaptivePromptRoute) -> AdaptiveContextPolicy:
    profile = _profile_for_route(route)
    allowed = [ContextSourceKind.USER_INPUT_SUMMARY]
    if profile.evidence_token_budget > 0:
        allowed.append(ContextSourceKind.WEB_SEARCH_EVIDENCE)
    if profile.memory_token_budget > 0:
        allowed.append(ContextSourceKind.MEMORY_PROJECTION)
    if profile.tool_schema_token_budget > 0:
        allowed.extend((ContextSourceKind.CAPABILITY_SCHEMA, ContextSourceKind.MCP_TOOL_SCHEMA))
    if profile.skill_token_budget > 0:
        allowed.append(ContextSourceKind.SKILL_PROMPT_CONTRIBUTION)
    allowed.append(ContextSourceKind.TOOL_RESULT)
    delivery = ContextDeliveryPolicy(max_candidates=profile.max_context_candidates, allowed_source_kinds=tuple(dict.fromkeys(allowed)))
    return AdaptiveContextPolicy(route=route, delivery_policy=delivery, budget=ContextBudget(max_context_tokens=profile.total_context_budget, reserved_response_tokens=profile.reserved_response_tokens), profile=profile)


def assemble_adaptive_prompt_harness(request: PromptAssemblyRequest) -> PromptAssemblyResult:
    route = _route_for_intent(request.intent_ref.intent_kind)
    profile = _profile_for_route(route)
    included = list(request.context_pack.included)
    sections: list[PromptSection] = [_system_policy_section(request.intent_ref)]
    if route in {AdaptivePromptRoute.TOOL_USE, AdaptivePromptRoute.BROWSER, AdaptivePromptRoute.MCP}:
        sections.append(_approval_policy_section(request.intent_ref))
    for kind in _section_order(route):
        sections.extend(_section_from_candidate(candidate) for candidate in included if _kind_for_candidate(candidate) == kind)
    if any(section.kind == PromptSectionKind.EVIDENCE_CONTEXT for section in sections):
        sections.append(_citation_guidance_section(request.intent_ref))
    sections.append(_response_contract_section(request.intent_ref))
    used = sum(section.token_estimate for section in sections if section.included)
    budget = PromptBudgetReport(max_context_tokens=request.context_pack.budget.max_context_tokens, used_context_tokens=used, section_count=len(sections), within_budget=used <= request.context_pack.budget.max_context_tokens)
    suppression = PromptBlockSuppression(
        evidence_block_suppressed=profile.evidence_token_budget == 0 or not any(section.kind == PromptSectionKind.EVIDENCE_CONTEXT for section in sections),
        memory_block_suppressed=profile.memory_token_budget == 0 or not any(section.kind == PromptSectionKind.MEMORY_CONTEXT for section in sections),
        tool_block_suppressed=profile.tool_schema_token_budget == 0 or not any(section.kind == PromptSectionKind.CAPABILITY_SCHEMA for section in sections),
        skill_block_suppressed=profile.skill_token_budget == 0 or not any(section.kind == PromptSectionKind.SKILL_CONTRIBUTION for section in sections),
    )
    return PromptAssemblyResult(
        schema_version=request.schema_version,
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        plan=PromptHarnessPlan(schema_version=request.schema_version, trace_id=request.trace_id, turn_id=request.turn_id, intent_ref=request.intent_ref, sections=tuple(sections), route_profile=profile, suppression=suppression),
        budget_report=budget,
    )


def tool_schema_context_candidate(
    manifest: CapabilityManifest,
    *,
    route: AdaptivePromptRoute,
    risk_level: ToolRiskLevel,
    approval_required: bool,
    eligible: bool,
) -> ContextCandidate:
    identifier = manifest.capability_ref.identifier if eligible else f"ineligible.{manifest.capability_ref.identifier}"
    kind = ContextSourceKind.MCP_TOOL_SCHEMA if manifest.capability_ref.kind.value == "mcp_tool" else ContextSourceKind.CAPABILITY_SCHEMA
    safe_schema_keys = sorted((manifest.input_schema or {}).keys())
    content = f"tool={manifest.capability_ref.identifier}; purpose={manifest.description}; schema_keys={safe_schema_keys}; risk={risk_level.value}; approval_required={approval_required}"
    return ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=kind, identifier=identifier),
        content,
        token_estimate=max(20, len(content.split()) + 10),
        intent_tags=(_intent_tag_for_route(route),) if eligible else ("ineligible",),
        trust_level=ContextSourceTrustLevel.INTERNAL_SAFE_PROJECTION,
    )


def _profile_for_route(route: AdaptivePromptRoute) -> PromptRouteProfile:
    profiles = {
        AdaptivePromptRoute.GROUNDED_LOOKUP: PromptRouteProfile(route=route.value, total_context_budget=2400, evidence_token_budget=1000, memory_token_budget=240, tool_schema_token_budget=120, skill_token_budget=160, reserved_response_tokens=700, max_context_candidates=12),
        AdaptivePromptRoute.MEMORY_QUERY: PromptRouteProfile(route=route.value, total_context_budget=2200, evidence_token_budget=350, memory_token_budget=900, tool_schema_token_budget=80, skill_token_budget=160, reserved_response_tokens=600, max_context_candidates=12),
        AdaptivePromptRoute.TOOL_USE: PromptRouteProfile(route=route.value, total_context_budget=1800, evidence_token_budget=160, memory_token_budget=120, tool_schema_token_budget=800, skill_token_budget=180, reserved_response_tokens=500, max_context_candidates=10),
        AdaptivePromptRoute.BROWSER: PromptRouteProfile(route=route.value, total_context_budget=1900, evidence_token_budget=180, memory_token_budget=120, tool_schema_token_budget=700, skill_token_budget=140, reserved_response_tokens=500, max_context_candidates=10),
        AdaptivePromptRoute.MCP: PromptRouteProfile(route=route.value, total_context_budget=1900, evidence_token_budget=160, memory_token_budget=120, tool_schema_token_budget=850, skill_token_budget=140, reserved_response_tokens=500, max_context_candidates=10),
        AdaptivePromptRoute.CLARIFICATION: PromptRouteProfile(route=route.value, total_context_budget=500, evidence_token_budget=0, memory_token_budget=0, tool_schema_token_budget=0, skill_token_budget=0, reserved_response_tokens=200, max_context_candidates=2),
    }
    return profiles.get(route, PromptRouteProfile(route=AdaptivePromptRoute.SIMPLE_CHAT.value, total_context_budget=800, evidence_token_budget=0, memory_token_budget=80, tool_schema_token_budget=0, skill_token_budget=80, reserved_response_tokens=300, max_context_candidates=4))


def _route_for_intent(kind: IntentKind) -> AdaptivePromptRoute:
    if kind in {IntentKind.WEB_SEARCH, IntentKind.GROUNDED_ANSWER}:
        return AdaptivePromptRoute.GROUNDED_LOOKUP
    if kind in {IntentKind.MEMORY, IntentKind.MEMORY_TREE_NEEDED}:
        return AdaptivePromptRoute.MEMORY_QUERY
    if kind == IntentKind.CAPABILITY_TOOL:
        return AdaptivePromptRoute.TOOL_USE
    if kind == IntentKind.BROWSER_COMPUTER_USE:
        return AdaptivePromptRoute.BROWSER
    if kind == IntentKind.MCP_NEEDED:
        return AdaptivePromptRoute.MCP
    if kind == IntentKind.CLARIFICATION:
        return AdaptivePromptRoute.CLARIFICATION
    return AdaptivePromptRoute.SIMPLE_CHAT


def _section_order(route: AdaptivePromptRoute) -> tuple[PromptSectionKind, ...]:
    if route == AdaptivePromptRoute.GROUNDED_LOOKUP:
        return (PromptSectionKind.EVIDENCE_CONTEXT, PromptSectionKind.MEMORY_CONTEXT, PromptSectionKind.SKILL_CONTRIBUTION, PromptSectionKind.CAPABILITY_SCHEMA, PromptSectionKind.USER_CONTEXT, PromptSectionKind.TOOL_RESULT)
    if route == AdaptivePromptRoute.MEMORY_QUERY:
        return (PromptSectionKind.MEMORY_CONTEXT, PromptSectionKind.EVIDENCE_CONTEXT, PromptSectionKind.SKILL_CONTRIBUTION, PromptSectionKind.CAPABILITY_SCHEMA, PromptSectionKind.USER_CONTEXT, PromptSectionKind.TOOL_RESULT)
    if route in {AdaptivePromptRoute.TOOL_USE, AdaptivePromptRoute.BROWSER, AdaptivePromptRoute.MCP}:
        return (PromptSectionKind.CAPABILITY_SCHEMA, PromptSectionKind.SKILL_CONTRIBUTION, PromptSectionKind.TOOL_RESULT, PromptSectionKind.MEMORY_CONTEXT, PromptSectionKind.EVIDENCE_CONTEXT, PromptSectionKind.USER_CONTEXT)
    return (PromptSectionKind.USER_CONTEXT, PromptSectionKind.SKILL_CONTRIBUTION, PromptSectionKind.MEMORY_CONTEXT, PromptSectionKind.TOOL_RESULT)


def _kind_for_candidate(candidate: ContextCandidate) -> PromptSectionKind:
    return _section_from_candidate(candidate).kind


def _intent_tag_for_route(route: AdaptivePromptRoute) -> str:
    return {
        AdaptivePromptRoute.TOOL_USE: IntentKind.CAPABILITY_TOOL.value,
        AdaptivePromptRoute.BROWSER: IntentKind.BROWSER_COMPUTER_USE.value,
        AdaptivePromptRoute.MCP: IntentKind.MCP_NEEDED.value,
        AdaptivePromptRoute.GROUNDED_LOOKUP: IntentKind.GROUNDED_ANSWER.value,
        AdaptivePromptRoute.MEMORY_QUERY: IntentKind.MEMORY_TREE_NEEDED.value,
    }.get(route, IntentKind.PROVIDER_SIMPLE_CHAT.value)


def _citation_guidance_section(intent_ref: IntentRef) -> PromptSection:
    return PromptSection(kind=PromptSectionKind.SYSTEM_POLICY, source_ref=ContextSourceRef(kind=ContextSourceKind.TRACE_TELEMETRY_SUMMARY, identifier="marvex.citation_policy"), safe_content="Cite only provided evidence refs such as [web.evidence.1] or [memory.evidence.chunk]. If evidence is missing, say evidence is missing or request search.", token_estimate=24, included=True, reason_code="section.citation_guidance")


def _approval_policy_section(intent_ref: IntentRef) -> PromptSection:
    return PromptSection(kind=PromptSectionKind.APPROVAL_STATE, source_ref=ContextSourceRef(kind=ContextSourceKind.TRACE_TELEMETRY_SUMMARY, identifier="marvex.approval_policy"), safe_content=f"For intent {intent_ref.intent_kind.value}, provider tool calls are proposals. Side-effect actions require CapabilityRuntime approval before execution.", token_estimate=22, included=True, reason_code="section.approval_policy")
