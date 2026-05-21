from __future__ import annotations

import contextlib
import io
from typing import Any

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
from packages.grounded_answer_runtime import web_search_bundle_to_context_candidate
from packages.intent_runtime import (
    IntentClassificationRequest,
    IntentKind,
    IntentRef,
    classify_intent,
)
from packages.memory_runtime import MemoryReadQuery
from packages.prompt_harness_runtime import PromptAssemblyRequest, assemble_prompt_harness
from packages.prompt_harness_runtime.adaptive import (
    AdaptivePromptRoute,
    adaptive_context_policy_for_route,
    assemble_adaptive_prompt_harness,
)
from packages.prompt_harness_runtime.models import (
    CompactionCandidate,
    MemoryOffloadDecision,
    ToolResultClearingDecision,
    decide_compaction,
)
from packages.web_search_runtime import WebSearchFreshness, WebSearchQuery

from .models import CognitionEvidenceRef, CognitionStep, CognitionStepPlan, CognitionTurnAssembly


class CognitionRuntime:
    def __init__(
        self,
        *,
        intent_classifier: Any | None = None,
        intent_planner: Any | None = None,
        memory_store: Any | None = None,
        memory_tree_runtime: Any | None = None,
        web_search_provider: Any | None = None,
        max_steps: int = 5,
    ) -> None:
        self._intent_classifier = intent_classifier or classify_intent
        self._intent_planner = intent_planner
        self._memory_store = memory_store
        self._memory_tree_runtime = memory_tree_runtime
        self._web_search_provider = web_search_provider
        self._max_steps = min(max(1, max_steps), 6)

    def assemble_turn(self, turn_input: Any) -> CognitionTurnAssembly:
        request = IntentClassificationRequest(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            user_input_summary=_bounded_input_summary(turn_input.user_visible_input),
        )
        intent = self._intent_classifier(request)
        intent_plan = self._intent_planner_or_default().plan(request)
        intent_ref = intent.selected_intent
        grounding_required = intent_ref.intent_kind in {IntentKind.GROUNDED_ANSWER, IntentKind.WEB_SEARCH}
        web_search_required = _web_search_required(intent_ref, intent.hybrid_details)
        candidates, web_bundle, web_refs, memory_refs = self._context_candidates(
            turn_input,
            intent_ref,
            web_search_required=web_search_required,
            grounding_required=grounding_required,
        )
        adaptive_policy = adaptive_context_policy_for_route(_adaptive_route_for_intent(intent_ref.intent_kind))
        candidates = _compact_candidates(candidates, max_tokens=max(120, adaptive_policy.profile.total_context_budget // 3))
        context_pack = adaptive_policy.build_pack(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            intent_ref=intent_ref,
            candidates=tuple(candidates),
        )
        prompt_result = assemble_adaptive_prompt_harness(
            PromptAssemblyRequest(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                turn_id=turn_input.turn_id,
                intent_ref=intent_ref,
                context_pack=context_pack,
            )
        )
        evidence_refs = tuple(
            CognitionEvidenceRef(ref_type="web_evidence", ref_id=ref.evidence_id, source=ref.domain)
            for ref in web_refs
        ) + tuple(
            CognitionEvidenceRef(ref_type="memory_evidence", ref_id=_memory_citation_id(ref), source=str(getattr(ref, "source_id", "memory")))
            for ref in memory_refs
        )
        step_plan = CognitionStepPlan(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            max_steps=self._max_steps,
            steps=_steps_for_intent(
                turn_input,
                intent_ref,
                web_search_required=web_search_required,
                grounding_required=grounding_required,
            ),
        )
        return CognitionTurnAssembly(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            intent_projection=intent.safe_projection(),
            context_pack=context_pack,
            context_projection=context_pack.safe_projection(),
            prompt_result=prompt_result,
            prompt_projection=prompt_result.safe_projection(),
            intent_plan=intent_plan,
            step_plan=step_plan,
            evidence_refs=evidence_refs,
            web_evidence_refs=web_refs,
            memory_evidence_refs=memory_refs,
            web_search_bundle=web_bundle,
            web_search_required=web_search_required,
            grounding_required=grounding_required,
        )

    def _context_candidates(
        self,
        turn_input: Any,
        intent_ref: IntentRef,
        *,
        web_search_required: bool,
        grounding_required: bool,
    ) -> tuple[list[ContextCandidate], Any | None, tuple[Any, ...], tuple[Any, ...]]:
        candidates = [
            ContextCandidate.from_safe_summary(
                ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier=f"input.{turn_input.turn_id}"),
                _route_summary(turn_input.user_visible_input, intent_ref.intent_kind),
                token_estimate=8,
                intent_tags=(intent_ref.intent_kind.value,),
                trust_level=ContextSourceTrustLevel.USER_SUMMARY,
            )
        ]
        if intent_ref.intent_kind == IntentKind.CAPABILITY_TOOL:
            eligibility = CapabilityEligibilityDecision(
                schema_version=turn_input.schema_version,
                decision_id=f"eligibility.{turn_input.turn_id}",
                capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"),
                eligible=True,
                reason_code="eligible.intent_selected",
                intent_tags=(IntentKind.CAPABILITY_TOOL.value,),
            )
            candidates.append(ContextCandidate.from_capability_schema(eligibility, token_estimate=8))
        for memory_record in self._memory_context_records(turn_input):
            candidates.append(_safe_memory_candidate(turn_input, intent_ref, memory_record))
        memory_refs = self._memory_tree_refs(turn_input) if grounding_required or intent_ref.intent_kind == IntentKind.MEMORY_TREE_NEEDED else ()
        for ref in memory_refs[:2]:
            candidates.append(
                ContextCandidate.from_safe_summary(
                    ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier=f"memory_tree.node.{getattr(ref, 'chunk_id', 'unknown')}"),
                    _bounded_input_summary(
                        f"Memory evidence from {getattr(ref, 'source_id', 'memory')} [{getattr(ref, 'chunk_id', 'unknown')}]: {getattr(ref, 'quote_preview', '')}"
                    ),
                    token_estimate=_estimate_tokens(str(getattr(ref, "quote_preview", ""))) + 12,
                    intent_tags=(intent_ref.intent_kind.value,),
                )
            )
        web_bundle = self._search_web(turn_input) if web_search_required else None
        web_refs = tuple(getattr(web_bundle, "evidence_refs", ()) or ())
        if web_bundle is not None:
            candidates.append(web_search_bundle_to_context_candidate(web_bundle))
        return candidates, web_bundle, web_refs, memory_refs

    def _memory_context_ref(self, turn_input: Any) -> str | None:
        records = self._memory_context_records(turn_input)
        return records[0].memory_ref.ref_id if records else None

    def _memory_context_records(self, turn_input: Any) -> tuple[Any, ...]:
        if self._memory_store is None or not hasattr(self._memory_store, "read") or turn_input.session_ref is None:
            return ()
        query = MemoryReadQuery(
            schema_version=turn_input.schema_version,
            query_id=f"memory-read.{turn_input.turn_id}",
            scope="session",
            session_ref=turn_input.session_ref,
            conversation_ref=None,
            max_records=3,
            policy_status="approved",
        )
        try:
            result = self._memory_store.read(query)
        except Exception:
            return ()
        return tuple(result.records)

    def _memory_tree_refs(self, turn_input: Any) -> tuple[Any, ...]:
        if self._memory_tree_runtime is None or not hasattr(self._memory_tree_runtime, "memory_query_with_evidence"):
            return ()
        try:
            search = self._memory_tree_runtime.memory_query_with_evidence(_bounded_input_summary(turn_input.user_visible_input))
        except Exception:
            return ()
        refs: list[Any] = []
        for node in tuple(getattr(search, "results", ()) or ())[:2]:
            refs.extend(tuple(getattr(node, "evidence_links", ()) or ())[:2])
        return tuple(refs)

    def _search_web(self, turn_input: Any) -> Any | None:
        if self._web_search_provider is None or not hasattr(self._web_search_provider, "search"):
            return None
        query = WebSearchQuery(
            query=turn_input.user_visible_input or _bounded_input_summary(turn_input.user_visible_input),
            freshness=_freshness_for(turn_input.user_visible_input),
            max_results=5,
        )
        try:
            return self._web_search_provider.search(query)
        except Exception:
            return None

    def _intent_planner_or_default(self) -> Any:
        if self._intent_planner is not None:
            return self._intent_planner
        with contextlib.redirect_stderr(io.StringIO()):
            from packages.intent_runtime.hybrid import HybridIntentRuntime

        self._intent_planner = HybridIntentRuntime.default()
        return self._intent_planner


def _web_search_required(intent_ref: IntentRef, hybrid_details: dict[str, object]) -> bool:
    return intent_ref.intent_kind in {IntentKind.WEB_SEARCH, IntentKind.GROUNDED_ANSWER} or bool(hybrid_details.get("freshness_needed"))


def _steps_for_intent(
    turn_input: Any,
    intent_ref: IntentRef,
    *,
    web_search_required: bool,
    grounding_required: bool,
) -> tuple[CognitionStep, ...]:
    steps = [CognitionStep(step_id=f"{turn_input.turn_id}:step.plan", step_kind="plan", reason_code="cognition.plan")]
    if intent_ref.intent_kind in {IntentKind.UNSAFE_OR_INJECTION_SUSPECTED, IntentKind.UNSAFE_RISKY}:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.block", step_kind="block", reason_code="intent.unsafe"))
    elif intent_ref.intent_kind == IntentKind.CLARIFICATION:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.clarify", step_kind="clarify", reason_code="intent.clarification"))
    elif intent_ref.intent_kind == IntentKind.CAPABILITY_TOOL:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.tool", step_kind="tool", reason_code="intent.capability_tool"))
    elif intent_ref.intent_kind == IntentKind.RISKY_ACTION:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.approval", step_kind="approval", reason_code="policy.approval_required"))
    elif web_search_required:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.web_search", step_kind="web_search", reason_code="freshness.web_search_required"))
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.grounded_answer", step_kind="grounded_answer", reason_code="grounding.required"))
    elif grounding_required:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.grounded_answer", step_kind="grounded_answer", reason_code="grounding.required"))
    else:
        steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.provider", step_kind="provider", reason_code="intent.provider"))
    steps.append(CognitionStep(step_id=f"{turn_input.turn_id}:step.finalize", step_kind="finalize", reason_code="cognition.finalize"))
    return tuple(steps)


def _safe_memory_candidate(turn_input: Any, intent_ref: IntentRef, record: Any) -> ContextCandidate:
    content = _bounded_input_summary(
        f"Recalled memory [{record.memory_ref.ref_id}] from turn {record.turn_id}: {record.content}"
    )
    return ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier=f"memory.{record.memory_ref.ref_id}"),
        content,
        token_estimate=_estimate_tokens(content),
        intent_tags=(),
    )


def _route_summary(text: str | None, intent_kind: IntentKind) -> str:
    actual = _bounded_input_summary(text)
    if intent_kind in {IntentKind.WEB_SEARCH, IntentKind.GROUNDED_ANSWER}:
        return f"User asked: {actual}"
    if intent_kind == IntentKind.CAPABILITY_TOOL:
        return f"User asked: {actual}"
    if intent_kind == IntentKind.RISKY_ACTION:
        return f"User asked: {actual}"
    if intent_kind == IntentKind.CLARIFICATION:
        return f"User asked: {actual}"
    return f"User asked: {actual}"


def _bounded_input_summary(text: str | None) -> str:
    value = (text or "").strip() or "empty turn"
    return value[:600]


def _estimate_tokens(text: str) -> int:
    return max(4, min(300, len(text.split()) + 4))


def _adaptive_route_for_intent(intent_kind: IntentKind) -> AdaptivePromptRoute:
    if intent_kind in {IntentKind.WEB_SEARCH, IntentKind.GROUNDED_ANSWER}:
        return AdaptivePromptRoute.GROUNDED_LOOKUP
    if intent_kind in {IntentKind.MEMORY, IntentKind.MEMORY_TREE_NEEDED}:
        return AdaptivePromptRoute.MEMORY_QUERY
    if intent_kind == IntentKind.CAPABILITY_TOOL:
        return AdaptivePromptRoute.TOOL_USE
    if intent_kind == IntentKind.BROWSER_COMPUTER_USE:
        return AdaptivePromptRoute.BROWSER
    if intent_kind == IntentKind.MCP_NEEDED:
        return AdaptivePromptRoute.MCP
    if intent_kind == IntentKind.CLARIFICATION:
        return AdaptivePromptRoute.CLARIFICATION
    return AdaptivePromptRoute.SIMPLE_CHAT


def _compact_candidates(candidates: list[ContextCandidate], *, max_tokens: int) -> list[ContextCandidate]:
    compacted: list[ContextCandidate] = []
    for candidate in candidates:
        compaction = decide_compaction(
            CompactionCandidate(
                source_ref=candidate.source_ref,
                token_estimate=candidate.token_estimate,
                retention_reason="current_user_intent",
                safe_summary=candidate.safe_summary,
            ),
            max_tokens=max_tokens,
        )
        ToolResultClearingDecision.from_candidate(
            CompactionCandidate(
                source_ref=candidate.source_ref,
                token_estimate=candidate.token_estimate,
                retention_reason="current_user_intent",
                safe_summary=candidate.safe_summary,
            )
        )
        MemoryOffloadDecision(source_ref=candidate.source_ref, offload_allowed=False, reason_code="memory_offload.not_mid_subtask")
        if compaction.strategy.value == "compact_safe_summary":
            compacted.append(
                candidate.model_copy(
                    update={
                        "safe_summary": candidate.safe_summary[:600],
                        "token_estimate": min(candidate.token_estimate, max_tokens),
                    }
                )
            )
        else:
            compacted.append(candidate)
    return compacted


def _freshness_for(text: str | None) -> WebSearchFreshness:
    lowered = (text or "").lower()
    if any(marker in lowered for marker in ("latest", "current", "today", "version", "release")):
        return WebSearchFreshness.CURRENT
    if "recent" in lowered:
        return WebSearchFreshness.RECENT
    return WebSearchFreshness.ANY


def _memory_citation_id(ref: Any) -> str:
    return "memory.evidence." + str(getattr(ref, "chunk_id", "unknown")).replace(":", "-")
