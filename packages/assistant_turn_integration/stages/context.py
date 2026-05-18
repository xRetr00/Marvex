from __future__ import annotations

import asyncio
from typing import Any

from packages.adapters.capabilities.mcp import McpAllowlist, McpClientSession, McpSdkAdapter, McpServerRef, McpToolListingProjection
from packages.capability_runtime import CapabilityEligibilityDecision, CapabilityKind, CapabilityRef
from packages.context_runtime import (
    ContextBudget,
    ContextCandidate,
    ContextDeliveryPolicy,
    ContextSourceKind,
    ContextSourceRef,
    ContextSourceTrustLevel,
    build_context_pack,
)
from packages.contracts import AssistantTurnInput
from packages.intent_runtime import IntentKind
from packages.memory_runtime import MemoryReadQuery


def _discover_mcp(mcp_session: McpClientSession | None, mcp_server_ref: McpServerRef | None, mcp_allowlist: McpAllowlist | None) -> tuple[McpToolListingProjection, ...]:
    if not mcp_session or not mcp_server_ref or not mcp_allowlist:
        return ()
    return asyncio.run(McpSdkAdapter(session=mcp_session, allowlist=mcp_allowlist).discover_tools(mcp_server_ref))


def _build_context(turn_input: AssistantTurnInput, intent_ref: Any, *, mcp_listings: tuple[McpToolListingProjection, ...] = (), memory_store: Any | None = None) -> Any:
    candidates: list[ContextCandidate] = [
        ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier=f"input.{turn_input.turn_id}"), _input_summary(turn_input), token_estimate=8, intent_tags=(intent_ref.intent_kind.value,), trust_level=ContextSourceTrustLevel.USER_SUMMARY),
    ]
    if intent_ref.intent_kind == IntentKind.CAPABILITY_TOOL:
        eligibility = CapabilityEligibilityDecision(schema_version=turn_input.schema_version, decision_id=f"eligibility.{turn_input.turn_id}", capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"), eligible=True, reason_code="eligible.intent_selected", intent_tags=(IntentKind.CAPABILITY_TOOL.value,))
        candidates.append(ContextCandidate.from_capability_schema(eligibility, token_estimate=8))
    elif intent_ref.intent_kind == IntentKind.MCP_NEEDED:
        for listing in mcp_listings:
            if listing.allowed:
                eligibility = CapabilityEligibilityDecision(schema_version=turn_input.schema_version, decision_id=f"eligibility.{listing.capability_ref.identifier}", capability_ref=listing.capability_ref, eligible=True, reason_code="eligible.mcp_allowlisted", intent_tags=(IntentKind.MCP_NEEDED.value,))
                candidates.append(ContextCandidate.from_capability_schema(eligibility, token_estimate=10))
    elif intent_ref.intent_kind == IntentKind.SKILL_NEEDED:
        candidates.append(ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.SKILL_PROMPT_CONTRIBUTION, identifier="skill.safe-writing"), "Skill safe-writing contributes bounded style guidance.", token_estimate=10, intent_tags=(IntentKind.SKILL_NEEDED.value,)))
    elif intent_ref.intent_kind == IntentKind.MEMORY:
        memory_ref = _memory_context_ref(turn_input, memory_store)
        memory_identifier = f"memory.{memory_ref}" if memory_ref else "memory.preference.short-answer"
        candidates.append(ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier=memory_identifier), "Approved memory preference ref is available.", token_estimate=8, intent_tags=(IntentKind.MEMORY.value,)))
    elif intent_ref.intent_kind == IntentKind.BROWSER_COMPUTER_USE:
        eligibility = CapabilityEligibilityDecision(schema_version=turn_input.schema_version, decision_id=f"eligibility.browser.{turn_input.turn_id}", capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click"), eligible=True, reason_code="eligible.browser_intent_requires_approval", intent_tags=(IntentKind.BROWSER_COMPUTER_USE.value,))
        candidates.append(ContextCandidate.from_capability_schema(eligibility, token_estimate=8))
    return build_context_pack(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, intent_ref=intent_ref, candidates=tuple(candidates), budget=ContextBudget(max_context_tokens=80, reserved_response_tokens=40), policy=ContextDeliveryPolicy(max_candidates=4, allowed_source_kinds=(ContextSourceKind.USER_INPUT_SUMMARY, ContextSourceKind.CAPABILITY_SCHEMA, ContextSourceKind.MCP_TOOL_SCHEMA, ContextSourceKind.SKILL_PROMPT_CONTRIBUTION, ContextSourceKind.MEMORY_PROJECTION), include_excluded_reasons=True))


def _input_summary(turn_input: AssistantTurnInput) -> str:
    text = (turn_input.user_visible_input or "").lower()
    if "click" in text or "browser" in text or "checkout" in text:
        return "User requested a browser action."
    if "mcp" in text:
        return "User requested an MCP server tool."
    if "skill" in text:
        return "User requested a skill package."
    if "remember" in text or "memory" in text or "preference" in text:
        return "User requested memory context."
    if "calculator" in text or "2+2" in text or "calculate" in text:
        return "User requested a safe calculator capability."
    return "User requested a simple assistant response."


def _memory_context_ref(turn_input: AssistantTurnInput, memory_store: Any | None) -> str | None:
    if memory_store is None or not hasattr(memory_store, "read") or turn_input.session_ref is None:
        return None
    query = MemoryReadQuery(schema_version=turn_input.schema_version, query_id=f"memory-read.{turn_input.turn_id}", scope="session", session_ref=turn_input.session_ref, conversation_ref=None, max_records=3, policy_status="approved")
    try:
        result = memory_store.read(query)
    except Exception:
        return None
    return result.records[0].memory_ref.ref_id if result.records else None


def _memory_ref_count(memory_store: Any | None) -> int:
    if memory_store is None or not hasattr(memory_store, "safe_inspect"):
        return 0
    return len(tuple(memory_store.safe_inspect(max_records=50)))


def _context_source_count(context_pack: Any, kind: ContextSourceKind) -> int:
    return len([candidate for candidate in context_pack.included if candidate.source_ref.kind == kind])
