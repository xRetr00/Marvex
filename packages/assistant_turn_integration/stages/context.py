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

class _WebSearchQuery(dict):
    def __init__(self, *, query: str, freshness: str, max_results: int) -> None:
        super().__init__(query=query, freshness=freshness, max_results=max_results, raw_query_persisted=False)

    def __getattr__(self, name: str) -> object:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

def _discover_mcp(mcp_session: McpClientSession | None, mcp_server_ref: McpServerRef | None, mcp_allowlist: McpAllowlist | None) -> tuple[McpToolListingProjection, ...]:
    if not mcp_session or not mcp_server_ref or not mcp_allowlist:
        return ()
    return asyncio.run(McpSdkAdapter(session=mcp_session, allowlist=mcp_allowlist).discover_tools(mcp_server_ref))

def _build_context(turn_input: AssistantTurnInput, intent_ref: Any, *, mcp_listings: tuple[McpToolListingProjection, ...] = (), memory_store: Any | None = None, memory_tree_runtime: Any | None = None, web_search_provider: Any | None = None) -> Any:
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
    elif intent_ref.intent_kind == IntentKind.MEMORY_TREE_NEEDED:
        candidates.extend(_memory_tree_context_candidates(turn_input, memory_tree_runtime))
    elif intent_ref.intent_kind in {IntentKind.GROUNDED_ANSWER, IntentKind.WEB_SEARCH}:
        candidates.extend(_web_evidence_context_candidates(turn_input, web_search_provider))
        if intent_ref.intent_kind == IntentKind.GROUNDED_ANSWER:
            candidates.extend(_memory_tree_context_candidates(turn_input, memory_tree_runtime, intent_kind=IntentKind.GROUNDED_ANSWER))
    elif intent_ref.intent_kind == IntentKind.BROWSER_COMPUTER_USE:
        eligibility = CapabilityEligibilityDecision(schema_version=turn_input.schema_version, decision_id=f"eligibility.browser.{turn_input.turn_id}", capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click"), eligible=True, reason_code="eligible.browser_intent_requires_approval", intent_tags=(IntentKind.BROWSER_COMPUTER_USE.value,))
        candidates.append(ContextCandidate.from_capability_schema(eligibility, token_estimate=8))
    return build_context_pack(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, intent_ref=intent_ref, candidates=tuple(candidates), budget=ContextBudget(max_context_tokens=160 if intent_ref.intent_kind in {IntentKind.GROUNDED_ANSWER, IntentKind.WEB_SEARCH} else 80, reserved_response_tokens=40), policy=ContextDeliveryPolicy(max_candidates=6, allowed_source_kinds=(ContextSourceKind.USER_INPUT_SUMMARY, ContextSourceKind.CAPABILITY_SCHEMA, ContextSourceKind.MCP_TOOL_SCHEMA, ContextSourceKind.SKILL_PROMPT_CONTRIBUTION, ContextSourceKind.MEMORY_PROJECTION, ContextSourceKind.WEB_SEARCH_EVIDENCE), include_excluded_reasons=True))

def _input_summary(turn_input: AssistantTurnInput) -> str:
    text = (turn_input.user_visible_input or "").lower()
    if "grounded answer" in text or "grounded" in text:
        summary = "User requested a grounded answer with evidence"
        if "latest" in text or "current" in text or "web" in text:
            summary += " and current web evidence"
        return summary + "."
    if "click" in text or "browser" in text or "checkout" in text:
        return "User requested a browser action."
    if "latest" in text or "current" in text or "web evidence" in text or "search" in text:
        return "User requested current web evidence."
    if "memory tree" in text or "source grounded" in text or "evidence" in text:
        return "User requested memory tree context."
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

def _memory_tree_context_candidates(turn_input: AssistantTurnInput, memory_tree_runtime: Any | None, *, intent_kind: IntentKind = IntentKind.MEMORY_TREE_NEEDED) -> tuple[ContextCandidate, ...]:
    if memory_tree_runtime is None or not hasattr(memory_tree_runtime, "memory_query_with_evidence"):
        return ()
    try:
        search = memory_tree_runtime.memory_query_with_evidence(_input_summary(turn_input))
    except Exception:
        return ()
    candidates: list[ContextCandidate] = []
    for node in tuple(getattr(search, "results", ()) or ())[:2]:
        evidence_links = tuple(getattr(node, "evidence_links", ()) or ())
        if not evidence_links:
            continue
        chunk_ids = ",".join(str(getattr(link, "chunk_id", "unknown")) for link in evidence_links[:3])
        source_ids = ",".join(str(getattr(link, "source_id", "unknown")) for link in evidence_links[:3])
        first_chunk_id = str(getattr(evidence_links[0], "chunk_id", getattr(node, "node_id", "unknown")))
        candidates.append(
            ContextCandidate.from_safe_summary(
                ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier=f"memory_tree.node.{first_chunk_id}"),
                f"Memory tree evidence ref available; node_id={getattr(node, 'node_id', 'unknown')}; evidence_count={len(evidence_links)}; source_ids={source_ids}; chunk_ids={chunk_ids}.",
                token_estimate=12,
                intent_tags=(intent_kind.value,),
            )
        )
    if hasattr(memory_tree_runtime, "memory_get_daily_digest"):
        try:
            digest = memory_tree_runtime.memory_get_daily_digest("current")
        except Exception:
            digest = None
        if digest is not None and getattr(digest, "evidence_links", ()):
            evidence_count = len(tuple(getattr(digest, "evidence_links", ()) or ()))
            candidates.append(
                ContextCandidate.from_safe_summary(
                    ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier="memory_tree.digest.current"),
                    f"Memory tree daily digest ref available; node_id={getattr(digest, 'node_id', 'daily:current')}; evidence_count={evidence_count}.",
                    token_estimate=10,
                    intent_tags=(intent_kind.value,),
                )
            )
    return tuple(candidates)

def _web_evidence_context_candidates(turn_input: AssistantTurnInput, web_search_provider: Any | None) -> tuple[ContextCandidate, ...]:
    if web_search_provider is None or not hasattr(web_search_provider, "search"):
        return ()
    freshness = "current" if any(marker in (turn_input.user_visible_input or "").lower() for marker in ("latest", "current", "recent", "version", "release")) else "any"
    try:
        bundle = web_search_provider.search(_WebSearchQuery(query=turn_input.user_visible_input or _input_summary(turn_input), freshness=freshness, max_results=5))
    except Exception:
        return ()
    return (_web_search_bundle_to_context_candidate(bundle),)

def _memory_tree_evidence_ref_count(context_pack: Any) -> int:
    return len([candidate for candidate in context_pack.included if candidate.source_ref.kind == ContextSourceKind.MEMORY_PROJECTION and candidate.source_ref.identifier.startswith("memory_tree.")])

def _web_search_bundle_to_context_candidate(bundle: Any) -> ContextCandidate:
    query = getattr(getattr(bundle, "query", None), "query", "query")
    lines: list[str] = []
    for ref in tuple(getattr(bundle, "evidence_refs", ()) or ())[:5]:
        evidence_id = str(getattr(ref, "evidence_id", "web.evidence.unknown"))
        title = str(getattr(ref, "title", "Untitled evidence"))
        source_url = str(getattr(ref, "source_url", getattr(ref, "url", "unknown")))
        snippet = str(getattr(ref, "snippet", ""))
        lines.append(f"[{evidence_id}] {title} - {source_url} - {snippet}")
    safe_summary = "\n".join(lines) or "No web evidence available."
    return ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=ContextSourceKind.WEB_SEARCH_EVIDENCE, identifier="web.bundle." + _safe_identifier(str(query))),
        safe_summary,
        token_estimate=max(1, len(safe_summary.split())),
        intent_tags=(IntentKind.GROUNDED_ANSWER.value, IntentKind.WEB_SEARCH.value),
        trust_level=ContextSourceTrustLevel.UNTRUSTED_SUMMARY,
    )


def _safe_identifier(value: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")
    return safe[:80] or "query"