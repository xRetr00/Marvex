from __future__ import annotations

from typing import Any

from packages.adapters.capabilities.mcp import McpAllowlist, McpClientSession, McpServerRef
from packages.adapters.providers.fake.fake_provider import FakeProvider, FakeProviderConfig
from packages.adapters.providers.tool_calls import ProviderToolCallSource
from packages.assistant_runtime.provider_stage import run_provider_stage_turn
from packages.context_runtime import ContextSourceKind
from packages.contracts import AssistantTurnInput, AssistantTurnResult, ConversationRef, TraceStage
from packages.intent_runtime import IntentClassificationRequest, IntentKind, classify_intent
from packages.prompt_harness_runtime import PlanningNeedDecision, PromptAssemblyRequest, assemble_prompt_harness
from packages.session_runtime import build_turn_linkage_from_assistant_turn_input
from packages.telemetry import TelemetrySink

from packages.assistant_turn_integration.models import EndToEndAssistantTurnResult
from packages.assistant_turn_integration.stages.context import _build_context, _discover_mcp, _input_summary, _memory_ref_count, _memory_tree_evidence_ref_count
from packages.assistant_turn_integration.stages.telemetry import _approval_status, _emit, _safe_ref, _telemetry_summary
from packages.assistant_turn_integration.stages.tools import _handle_browser_turn, _handle_calculator_turn, _handle_mcp_turn, _handle_provider_tool_call_turn
from packages.assistant_turn_integration.state import EndToEndTurnStateStore


def create_end_to_end_local_turn_handler(
    *,
    state_store: EndToEndTurnStateStore,
    provider: Any | None = None,
) -> Any:
    def handle_turn(request: Any) -> AssistantTurnResult:
        integrated = run_end_to_end_assistant_turn(
            request.assistant_turn_input,
            model=request.model,
            state_store=state_store,
            instructions=request.instructions,
            previous_response_id=request.previous_response_id,
            provider=provider,
        )
        return integrated.assistant_result

    return handle_turn


def _resolve_runtime_provider(provider: Any | None, *, fallback_text: str) -> Any:
    """Resolve the provider for a turn stage.

    Production callers inject a real ``ProviderPort`` instance. Test harnesses
    that pass ``None`` get a clearly labelled ``FakeProvider`` so the
    placeholder output is obvious in transcripts and trace dumps (no silent
    "the assistant feels stuck in stub mode"). The fake output text is
    prefixed with ``[STUB]`` so it's never mistaken for a real model reply.
    """

    if provider is not None:
        return provider
    return FakeProvider(FakeProviderConfig(output_text=f"[STUB] {fallback_text}"))


def run_end_to_end_assistant_turn(
    turn_input: AssistantTurnInput,
    *,
    model: str,
    state_store: EndToEndTurnStateStore | None = None,
    instructions: str | None = None,
    previous_response_id: str | None = None,
    mcp_session: McpClientSession | None = None,
    mcp_server_ref: McpServerRef | None = None,
    mcp_allowlist: McpAllowlist | None = None,
    resume_approval_request_id: str | None = None,
    provider_tool_call: dict[str, Any] | None = None,
    provider_tool_call_source: ProviderToolCallSource = ProviderToolCallSource.OPENAI_COMPATIBLE,
    browser_page: Any | None = None,
    intent_classifier: Any | None = None,
    memory_tree_runtime: Any | None = None,
    web_search_provider: Any | None = None,
    provider_continuation_provider: Any | None = None,
    provider: Any | None = None,
) -> EndToEndAssistantTurnResult:
    store = state_store or EndToEndTurnStateStore()
    telemetry_sink: TelemetrySink = store.trace_reader
    conversation_ref = ConversationRef(ref_type="conversation", ref_id=f"conversation.{turn_input.turn_id}")
    linkage = build_turn_linkage_from_assistant_turn_input(turn_input, conversation_ref=conversation_ref, previous_response_id=previous_response_id)
    _emit(telemetry_sink, turn_input, TraceStage.TURN_RECEIVED, "Integrated assistant turn received.", {"status": "received", "session_ref": _safe_ref(turn_input.session_ref), "conversation_ref": _safe_ref(conversation_ref)})

    intent_request = IntentClassificationRequest(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, user_input_summary=_input_summary(turn_input))
    classifier = intent_classifier or classify_intent
    intent = classifier(intent_request)
    intent_backend = str(getattr(intent, "backend_name", "deterministic"))
    library_owns_policy = bool(getattr(intent, "library_owns_policy", False))
    mcp_listings = _discover_mcp(mcp_session, mcp_server_ref, mcp_allowlist) if intent.selected_intent.intent_kind == IntentKind.MCP_NEEDED else ()
    context_pack = _build_context(turn_input, intent.selected_intent, mcp_listings=mcp_listings, memory_store=store.memory_store, memory_tree_runtime=memory_tree_runtime, web_search_provider=web_search_provider)
    prompt_result = assemble_prompt_harness(PromptAssemblyRequest(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, intent_ref=intent.selected_intent, context_pack=context_pack))
    planning = PlanningNeedDecision.from_intent(intent.selected_intent, context_candidate_count=len(context_pack.included) + len(context_pack.excluded))

    if provider_tool_call is not None:
        assistant_result, tool_projection, lifecycle_projection = _handle_provider_tool_call_turn(turn_input, model=model, instructions=instructions, previous_response_id=previous_response_id, telemetry_sink=telemetry_sink, raw_tool_call=provider_tool_call, source=provider_tool_call_source, memory_tree_evidence_ref_count=_memory_tree_evidence_ref_count(context_pack), provider_continuation_provider=provider_continuation_provider)
    elif intent.selected_intent.intent_kind == IntentKind.BROWSER_COMPUTER_USE:
        assistant_result, tool_projection, lifecycle_projection = _handle_browser_turn(turn_input, store, resume_approval_request_id, browser_page=browser_page)
    elif intent.selected_intent.intent_kind == IntentKind.MCP_NEEDED and mcp_session and mcp_server_ref and mcp_allowlist:
        assistant_result, tool_projection, lifecycle_projection, mcp_summary = _handle_mcp_turn(turn_input, model=model, instructions=instructions, previous_response_id=previous_response_id, telemetry_sink=telemetry_sink, mcp_session=mcp_session, mcp_server_ref=mcp_server_ref, mcp_allowlist=mcp_allowlist, listings=mcp_listings)
        store.last_mcp_summary = mcp_summary
    elif intent.selected_intent.intent_kind == IntentKind.CAPABILITY_TOOL:
        assistant_result, tool_projection, lifecycle_projection = _handle_calculator_turn(turn_input, model=model, instructions=instructions, previous_response_id=previous_response_id, telemetry_sink=telemetry_sink)
    elif intent.selected_intent.intent_kind == IntentKind.GROUNDED_ANSWER:
        assistant_result, tool_projection, lifecycle_projection = _handle_grounded_answer_turn(
            turn_input,
            context_pack,
            model=model,
            instructions=instructions,
            previous_response_id=previous_response_id,
            telemetry_sink=telemetry_sink,
            provider=provider,
        )
    else:
        provider_result = run_provider_stage_turn(turn_input, provider=_resolve_runtime_provider(provider, fallback_text="I can continue with the selected safe context."), model=model, instructions=instructions, previous_response_id=previous_response_id, provider_options={}, telemetry_sink=telemetry_sink)
        assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "prompt_section_count": prompt_result.safe_projection().section_count, "context_included_count": context_pack.safe_projection().included_count}}})
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": True, "final_response_ready": True, "result_status": "not_executed", "raw_payload_persisted": False}
        lifecycle_projection = {"trace_id": turn_input.trace_id, "turn_id": turn_input.turn_id, "tool_result_delivery_ready": False, "raw_payload_persisted": False}

    telemetry_summary = _telemetry_summary(prompt_result, intent.confidence.bucket.value, context_pack, planning.planning_needed, tool_projection)
    _emit(telemetry_sink, turn_input, TraceStage.TURN_COMPLETED, "Integrated assistant turn completed.", {"status": "completed", "session_ref": _safe_ref(turn_input.session_ref), "conversation_ref": _safe_ref(conversation_ref), "tool_status": str(tool_projection.get("result_status", "not_executed")), "approval_status": _approval_status(tool_projection), "provider_tool_proposal_count": 1 if tool_projection.get("provider_tool_proposal_id") else 0, "provider_continuation_input_ready": bool(tool_projection.get("provider_continuation_input_ready", False)), "provider_final_response_status": tool_projection.get("provider_final_response_status"), "raw_tool_output_persisted": False, "raw_provider_payload_persisted": False})

    trace = store.trace_reader.read_trace(turn_input.trace_id)
    control_summary = {
        "telemetry_event_count": (trace or {}).get("event_count", 0),
        "pending_approval_count": store.approval_store.list_pending().pending_count,
        "approved_count": store.approval_store.approved_count(),
        "denied_count": store.approval_store.denied_count(),
        "mcp_tool_count": int(tool_projection.get("mcp_tool_count", 0) or 0),
        "memory_ref_count": _memory_ref_count(store.memory_store),
        "memory_tree_evidence_ref_count": _memory_tree_evidence_ref_count(context_pack),
        "intent_backend": intent_backend,
        "library_owns_policy": library_owns_policy,
        "provider_tool_proposal_count": 1 if tool_projection.get("provider_tool_proposal_id") else 0,
        "provider_continuation_input_ready": bool(tool_projection.get("provider_continuation_input_ready", False)),
        "provider_final_response_status": tool_projection.get("provider_final_response_status"),
        "approval_state": _approval_status(tool_projection),
        "raw_payload_persisted": False,
    }
    integrated = EndToEndAssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_result=assistant_result,
        intent_projection=intent.safe_projection(),
        context_projection=context_pack.safe_projection(),
        prompt_projection=prompt_result.safe_projection(),
        tool_state_projection=tool_projection,
        lifecycle_projection={**lifecycle_projection, "session_linkage": linkage.safe_projection()},
        telemetry_summary=telemetry_summary,
        control_plane_summary=control_summary,
    )
    store.record_result(integrated)
    return integrated


def _handle_grounded_answer_turn(
    turn_input: AssistantTurnInput,
    context_pack: Any,
    *,
    model: str,
    instructions: str | None,
    previous_response_id: str | None,
    telemetry_sink: TelemetrySink,
    provider: Any | None = None,
) -> tuple[AssistantTurnResult, dict[str, Any], dict[str, Any]]:
    web_ids = _web_evidence_ids(context_pack)
    memory_links = _memory_evidence_links(context_pack)
    citation_ids = web_ids + tuple(_memory_citation_id(link) for link in memory_links)
    if not citation_ids:
        reason_code = "citation.evidence_missing"
        assistant_result = run_provider_stage_turn(
            turn_input,
            provider=_resolve_runtime_provider(provider, fallback_text="Evidence is missing for this grounded answer."),
            model=model,
            instructions=instructions,
            previous_response_id=previous_response_id,
            provider_options={"grounding_evidence_missing": True, "raw_evidence_persisted": False},
            telemetry_sink=telemetry_sink,
        ).model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "citation_validation": reason_code}}})
        return assistant_result, {"pending_approval_count": 0, "provider_continuation_ready": False, "final_response_ready": True, "result_status": "evidence_missing", "web_evidence_count": 0, "memory_evidence_count": 0, "citation_validation": reason_code, "raw_payload_persisted": False}, {"tool_result_delivery_ready": False, "raw_payload_persisted": False}
    reason_code = _validate_citation_ids(citation_ids[:4], allowed_ids=citation_ids)
    assistant_result = run_provider_stage_turn(
        turn_input,
        provider=_resolve_runtime_provider(provider, fallback_text="Grounded answer placeholder."),
        model=model,
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options={"grounded_citation_ids": list(citation_ids[:4]), "raw_evidence_persisted": False},
        telemetry_sink=telemetry_sink,
    ).model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "citation_validation": reason_code}}})
    return assistant_result, {"pending_approval_count": 0, "provider_continuation_ready": True, "final_response_ready": True, "result_status": "succeeded", "web_evidence_count": len(web_ids), "memory_evidence_count": len(memory_links), "citation_validation": reason_code, "raw_payload_persisted": False}, {"tool_result_delivery_ready": True, "raw_payload_persisted": False}


def _web_evidence_ids(context_pack: Any) -> tuple[str, ...]:
    ids: list[str] = []
    for candidate in context_pack.included:
        if candidate.source_ref.kind != ContextSourceKind.WEB_SEARCH_EVIDENCE:
            continue
        for word in str(candidate.safe_summary).replace("[", " ").replace("]", " ").split():
            if word.startswith("web.evidence."):
                ids.append(word.strip(".,;:"))
    return tuple(dict.fromkeys(ids))


def _memory_evidence_links(context_pack: Any) -> tuple[str, ...]:
    links: list[str] = []
    for candidate in context_pack.included:
        if candidate.source_ref.kind != ContextSourceKind.MEMORY_PROJECTION or not candidate.source_ref.identifier.startswith("memory_tree."):
            continue
        chunk_id = candidate.source_ref.identifier.removeprefix("memory_tree.node.")
        if chunk_id and chunk_id != candidate.source_ref.identifier:
            links.append(chunk_id)
    return tuple(links)


def _memory_citation_id(ref: object) -> str:
    return "memory.evidence." + str(ref).replace(":", "-")

def _validate_citation_ids(citation_ids: tuple[str, ...], *, allowed_ids: tuple[str, ...]) -> str:
    allowed = set(allowed_ids)
    return "citation.validated" if citation_ids and all(citation in allowed for citation in citation_ids) else "citation.evidence_ref_missing"
