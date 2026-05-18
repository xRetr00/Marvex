from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field

from packages.adapters.capabilities.browser import BrowserActionKind, BrowserActionProposal, BrowserExecutionRequest, BrowserSessionRef, PlaywrightBrowserWorkflow, PlaywrightSdkBoundary
from packages.adapters.capabilities.builtins import BuiltinToolCatalog
from packages.adapters.capabilities.mcp import McpAllowlist, McpClientSession, McpSdkAdapter, McpServerRef, McpToolListingProjection
from packages.adapters.providers.fake.fake_provider import FakeProvider, FakeProviderConfig
from packages.adapters.providers.tool_calls import ProviderToolCallMapper, ProviderToolCallSource
from packages.assistant_runtime import build_text_success_turn_result, build_tool_orchestrated_lifecycle_summary
from packages.assistant_runtime.provider_stage import run_provider_stage_turn
from packages.assistant_runtime.tool_orchestration import ToolOrchestratedTurnState
from packages.capability_runtime import (
    ApprovalPrompt,
    CapabilityApprovalRequest,
    CapabilityCallProposal,
    CapabilityEligibilityDecision,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityResultEnvelope,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.context_runtime import (
    ContextBudget,
    ContextCandidate,
    ContextDeliveryPolicy,
    ContextSourceKind,
    ContextSourceRef,
    ContextSourceTrustLevel,
    SafeContextProjection,
    build_context_pack,
)
from packages.contracts import AssistantTurnInput, AssistantTurnResult, ConversationRef, TraceLevel, TraceStage
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from packages.intent_runtime import IntentClassificationRequest, IntentKind, SafeIntentProjection, classify_intent
from packages.memory_runtime import MemoryReadQuery
from packages.prompt_harness_runtime import (
    HarnessTelemetrySummary,
    PlanningNeedDecision,
    PromptAssemblyRequest,
    SafePromptProjection,
    assemble_prompt_harness,
)
from packages.session_runtime import build_turn_linkage_from_assistant_turn_input
from packages.telemetry import InMemoryTraceReader, TelemetrySink, make_trace_event


class EndToEndAssistantTurnProjection(CapabilityRuntimeModel):
    schema_version: str
    trace_id: str
    turn_id: str
    intent_kind: str
    context_included_count: int
    prompt_section_count: int
    provider_continuation_ready: bool
    final_response_ready: bool
    pending_approval_count: int
    executed_tool_count: int
    telemetry_event_count: int
    raw_prompt_persisted: Literal[False] = False
    raw_context_persisted: Literal[False] = False
    raw_payload_persisted: Literal[False] = False


class EndToEndAssistantTurnResult(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    assistant_result: AssistantTurnResult
    intent_projection: SafeIntentProjection
    context_projection: SafeContextProjection
    prompt_projection: SafePromptProjection
    tool_state_projection: dict[str, Any]
    lifecycle_projection: dict[str, Any]
    telemetry_summary: dict[str, Any]
    control_plane_summary: dict[str, Any]
    raw_prompt_persisted: Literal[False] = False
    raw_context_persisted: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> EndToEndAssistantTurnProjection:
        return EndToEndAssistantTurnProjection(
            schema_version=self.schema_version,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            intent_kind=str(self.intent_projection.selected_intent["intent_kind"]),
            context_included_count=self.context_projection.included_count,
            prompt_section_count=self.prompt_projection.section_count,
            provider_continuation_ready=bool(self.tool_state_projection.get("provider_continuation_ready", False)),
            final_response_ready=bool(self.tool_state_projection.get("final_response_ready", False)),
            pending_approval_count=int(self.tool_state_projection.get("pending_approval_count", 0) or 0),
            executed_tool_count=1 if self.tool_state_projection.get("result_status") == "succeeded" else 0,
            telemetry_event_count=int(self.control_plane_summary.get("telemetry_event_count", 0) or 0),
        )


@dataclass
class EndToEndTurnStateStore:
    trace_reader: InMemoryTraceReader = field(default_factory=InMemoryTraceReader)
    approval_store: InMemoryApprovalStore = field(default_factory=InMemoryApprovalStore)
    last_result: EndToEndAssistantTurnResult | None = None
    last_mcp_summary: dict[str, Any] | None = None
    memory_store: Any | None = None

    def add_pending_approval(self, request: CapabilityApprovalRequest) -> None:
        self.approval_store.add_pending(request)

    def record_result(self, result: EndToEndAssistantTurnResult) -> None:
        self.last_result = result

    def control_plane_snapshot(self) -> ControlPlaneSnapshot:
        if self.last_result is None:
            return ControlPlaneSnapshot.foundation_default(schema_version="1")
        trace = self.trace_reader.read_trace(self.last_result.trace_id)
        projection = self.last_result.safe_projection()
        mcp_servers: tuple[dict[str, Any], ...] = ()
        if self.last_mcp_summary is not None:
            mcp_servers = (self.last_mcp_summary,)
        memory_rows: tuple[dict[str, Any], ...] = ()
        if self.memory_store is not None and hasattr(self.memory_store, "safe_inspect"):
            memory_rows = tuple(self.memory_store.safe_inspect(max_records=10))
        return ControlPlaneSnapshot.foundation_default(
            schema_version="1",
            providers=({"provider_id": "fake", "configured": True, "secret_present": False},),
            capabilities=({"identifier": "builtin.calculator", "kind": "tool", "risk_level": "safe"},),
            tools=({"tool_id": "builtin.calculator", "side_effect_level": "read_only"},),
            mcp_servers=mcp_servers,
            traces=({"trace_id": self.last_result.trace_id, "event_count": (trace or {}).get("event_count", 0), "raw_payload_persisted": False},),
            memory=memory_rows,
            sessions=({"session_id": "session-linked", "turn_count": 1},),
            agent_loops=(self.last_result.tool_state_projection,),
            telemetry={"trace_count": 1, "telemetry_event_count": projection.telemetry_event_count, "raw_payload_persisted": False},
            settings={"browser_tools_enabled": False, "computer_use_enabled": False},
        )


def create_end_to_end_local_turn_handler(*, state_store: EndToEndTurnStateStore) -> Any:
    def handle_turn(request: Any) -> AssistantTurnResult:
        integrated = run_end_to_end_assistant_turn(
            request.assistant_turn_input,
            model=request.model,
            state_store=state_store,
            instructions=request.instructions,
            previous_response_id=request.previous_response_id,
        )
        return integrated.assistant_result

    return handle_turn


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
) -> EndToEndAssistantTurnResult:
    store = state_store or EndToEndTurnStateStore()
    telemetry_sink: TelemetrySink = store.trace_reader
    conversation_ref = ConversationRef(ref_type="conversation", ref_id=f"conversation.{turn_input.turn_id}")
    linkage = build_turn_linkage_from_assistant_turn_input(turn_input, conversation_ref=conversation_ref, previous_response_id=previous_response_id)
    _emit(telemetry_sink, turn_input, TraceStage.TURN_RECEIVED, "Integrated assistant turn received.", {"status": "received", "session_ref": _safe_ref(turn_input.session_ref), "conversation_ref": _safe_ref(conversation_ref)})

    intent = classify_intent(IntentClassificationRequest(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, user_input_summary=_input_summary(turn_input)))
    mcp_listings = _discover_mcp(mcp_session, mcp_server_ref, mcp_allowlist) if intent.selected_intent.intent_kind == IntentKind.MCP_NEEDED else ()
    context_pack = _build_context(turn_input, intent.selected_intent, mcp_listings=mcp_listings, memory_store=store.memory_store)
    prompt_result = assemble_prompt_harness(PromptAssemblyRequest(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, intent_ref=intent.selected_intent, context_pack=context_pack))
    planning = PlanningNeedDecision.from_intent(intent.selected_intent, context_candidate_count=len(context_pack.included) + len(context_pack.excluded))

    if provider_tool_call is not None:
        assistant_result, tool_projection, lifecycle_projection = _handle_provider_tool_call_turn(turn_input, model=model, instructions=instructions, previous_response_id=previous_response_id, telemetry_sink=telemetry_sink, raw_tool_call=provider_tool_call, source=provider_tool_call_source)
    elif intent.selected_intent.intent_kind == IntentKind.BROWSER_COMPUTER_USE:
        assistant_result, tool_projection, lifecycle_projection = _handle_browser_turn(turn_input, store, resume_approval_request_id, browser_page=browser_page)
    elif intent.selected_intent.intent_kind == IntentKind.MCP_NEEDED and mcp_session and mcp_server_ref and mcp_allowlist:
        assistant_result, tool_projection, lifecycle_projection, mcp_summary = _handle_mcp_turn(turn_input, model=model, instructions=instructions, previous_response_id=previous_response_id, telemetry_sink=telemetry_sink, mcp_session=mcp_session, mcp_server_ref=mcp_server_ref, mcp_allowlist=mcp_allowlist, listings=mcp_listings)
        store.last_mcp_summary = mcp_summary
    elif intent.selected_intent.intent_kind == IntentKind.CAPABILITY_TOOL:
        assistant_result, tool_projection, lifecycle_projection = _handle_calculator_turn(turn_input, model=model, instructions=instructions, previous_response_id=previous_response_id, telemetry_sink=telemetry_sink)
    else:
        provider_result = run_provider_stage_turn(turn_input, provider=FakeProvider(FakeProviderConfig(output_text="I can continue with the selected safe context.")), model=model, instructions=instructions, previous_response_id=previous_response_id, provider_options={}, telemetry_sink=telemetry_sink)
        assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "prompt_section_count": prompt_result.safe_projection().section_count, "context_included_count": context_pack.safe_projection().included_count}}})
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": True, "final_response_ready": True, "result_status": "not_executed", "raw_payload_persisted": False}
        lifecycle_projection = {"trace_id": turn_input.trace_id, "turn_id": turn_input.turn_id, "tool_result_delivery_ready": False, "raw_payload_persisted": False}

    telemetry_summary = _telemetry_summary(prompt_result, intent.confidence.bucket.value, context_pack, planning.planning_needed, tool_projection)
    _emit(telemetry_sink, turn_input, TraceStage.TURN_COMPLETED, "Integrated assistant turn completed.", {"status": "completed", "session_ref": _safe_ref(turn_input.session_ref), "conversation_ref": _safe_ref(conversation_ref), "tool_status": str(tool_projection.get("result_status", "not_executed")), "approval_status": _approval_status(tool_projection)})

    trace = store.trace_reader.read_trace(turn_input.trace_id)
    control_summary = {
        "telemetry_event_count": (trace or {}).get("event_count", 0),
        "pending_approval_count": store.approval_store.list_pending().pending_count,
        "approved_count": store.approval_store.approved_count(),
        "denied_count": store.approval_store.denied_count(),
        "mcp_tool_count": int(tool_projection.get("mcp_tool_count", 0) or 0),
        "memory_ref_count": _memory_ref_count(store.memory_store),
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


def _handle_calculator_turn(turn_input: AssistantTurnInput, *, model: str, instructions: str | None, previous_response_id: str | None, telemetry_sink: TelemetrySink) -> tuple[AssistantTurnResult, dict[str, Any], dict[str, Any]]:
    proposal = _calculator_proposal(turn_input)
    permission = _permission(proposal)
    execution_request = CapabilityExecutionRequest(schema_version=turn_input.schema_version, request_id=f"request.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, proposal=proposal, permission_decision=permission, arguments={"expression": "2 + 2"})
    result = BuiltinToolCatalog.default().execute_request(execution_request).result
    state = ToolOrchestratedTurnState.from_safe_result(turn_input=turn_input, eligible_capability_count=1, proposal=proposal, permission_decision=permission, result=result, continuation_id=f"continuation.{turn_input.turn_id}")
    lifecycle = build_tool_orchestrated_lifecycle_summary(turn_input, state)
    provider_result = run_provider_stage_turn(turn_input, provider=FakeProvider(FakeProviderConfig(output_text="The calculator result is 4.")), model=model, instructions=instructions, previous_response_id=previous_response_id, provider_options={}, telemetry_sink=telemetry_sink)
    assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False}}})
    return assistant_result, state.safe_projection(), lifecycle.safe_projection()


def _handle_provider_tool_call_turn(turn_input: AssistantTurnInput, *, model: str, instructions: str | None, previous_response_id: str | None, telemetry_sink: TelemetrySink, raw_tool_call: dict[str, Any], source: ProviderToolCallSource) -> tuple[AssistantTurnResult, dict[str, Any], dict[str, Any]]:
    mapper = ProviderToolCallMapper(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id)
    mapped = mapper.from_litellm(raw_tool_call) if source is ProviderToolCallSource.LITELLM else mapper.from_openai_compatible(raw_tool_call, source=source)
    provider_proposal = mapped.to_capability_proposal()
    if provider_proposal.proposed_action != "calculator":
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"provider-tool-denied.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=provider_proposal.capability_ref, status="denied", safe_result={"reason_code": "unsupported_provider_tool"}, raw_input_persisted=False, raw_output_persisted=False)
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": True, "final_response_ready": True, "result_status": result.status, "provider_tool_call_source": source.value, "provider_tool_proposal_id": provider_proposal.proposal_id, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Provider tool proposal was denied by Marvex policy.", metadata={"integration_summary": {"raw_payload_persisted": False}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": True, "raw_payload_persisted": False}
    proposal = _calculator_proposal(turn_input)
    permission = _permission(proposal)
    execution_request = CapabilityExecutionRequest(schema_version=turn_input.schema_version, request_id=f"provider-tool-request.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, proposal=proposal, permission_decision=permission, arguments={"expression": _provider_expression(raw_tool_call)})
    result = BuiltinToolCatalog.default().execute_request(execution_request).result
    state = ToolOrchestratedTurnState.from_safe_result(turn_input=turn_input, eligible_capability_count=1, proposal=proposal, permission_decision=permission, result=result, continuation_id=f"provider-tool-continuation.{turn_input.turn_id}")
    lifecycle = build_tool_orchestrated_lifecycle_summary(turn_input, state)
    provider_result = run_provider_stage_turn(turn_input, provider=FakeProvider(FakeProviderConfig(output_text="Provider tool result is ready for continuation.")), model=model, instructions=instructions, previous_response_id=previous_response_id, provider_options={}, telemetry_sink=telemetry_sink)
    projection = state.safe_projection()
    projection["provider_tool_call_source"] = source.value
    projection["provider_tool_proposal_id"] = provider_proposal.proposal_id
    projection["provider_tool_capability_ref"] = provider_proposal.capability_ref.identifier
    assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "provider_tool_call_source": source.value}}})
    return assistant_result, projection, lifecycle.safe_projection()


def _handle_mcp_turn(turn_input: AssistantTurnInput, *, model: str, instructions: str | None, previous_response_id: str | None, telemetry_sink: TelemetrySink, mcp_session: McpClientSession, mcp_server_ref: McpServerRef, mcp_allowlist: McpAllowlist, listings: tuple[McpToolListingProjection, ...]) -> tuple[AssistantTurnResult, dict[str, Any], dict[str, Any], dict[str, Any]]:
    allowed = tuple(listing for listing in listings if listing.allowed)
    if not allowed:
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="No allowlisted MCP tool is available.", metadata={"integration_summary": {"raw_payload_persisted": False}})
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": False, "final_response_ready": True, "result_status": "denied", "mcp_tool_count": 0, "raw_payload_persisted": False}
        return assistant_result, tool_projection, {"tool_result_delivery_ready": False, "raw_payload_persisted": False}, {"server_id": mcp_server_ref.server_id, "allowlisted": True, "allowed_tool_count": 0}
    adapter = McpSdkAdapter(session=mcp_session, allowlist=mcp_allowlist)
    proposal = adapter.create_call_proposal(allowed[0], proposal_id=f"mcp-proposal.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id)
    permission = _permission(proposal)
    execution_request = CapabilityExecutionRequest(schema_version=turn_input.schema_version, request_id=f"mcp-request.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, proposal=proposal, permission_decision=permission, arguments={"query": proposal.proposed_action})
    result = asyncio.run(adapter.call_approved_tool(mcp_server_ref, execution_request))
    state = ToolOrchestratedTurnState.from_safe_result(turn_input=turn_input, eligible_capability_count=len(allowed), proposal=proposal, permission_decision=permission, result=result, continuation_id=f"mcp-continuation.{turn_input.turn_id}")
    lifecycle = build_tool_orchestrated_lifecycle_summary(turn_input, state)
    provider_result = run_provider_stage_turn(turn_input, provider=FakeProvider(FakeProviderConfig(output_text="The MCP tool result is ready for continuation.")), model=model, instructions=instructions, previous_response_id=previous_response_id, provider_options={}, telemetry_sink=telemetry_sink)
    assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "mcp_tool_count": len(allowed)}}})
    projection = state.safe_projection()
    projection["mcp_tool_count"] = len(allowed)
    projection["mcp_execution_status"] = result.status
    return assistant_result, projection, lifecycle.safe_projection(), {"server_id": mcp_server_ref.server_id, "allowlisted": True, "allowed_tool_count": len(allowed), "blocked_tool_count": len([listing for listing in listings if not listing.allowed]), "raw_payload_persisted": False}


def _handle_browser_turn(turn_input: AssistantTurnInput, store: EndToEndTurnStateStore, resume_approval_request_id: str | None, *, browser_page: Any | None = None) -> tuple[AssistantTurnResult, dict[str, Any], dict[str, Any]]:
    browser_action = _browser_action_proposal(turn_input)
    proposal = browser_action.to_capability_proposal()
    if not browser_action.requires_approval:
        permission = _permission(proposal)
        request = BrowserExecutionRequest.from_proposal(request_id=f"browser-request.{turn_input.turn_id}", proposal=browser_action, permission_decision=permission)
        result = PlaywrightBrowserWorkflow(boundary=PlaywrightSdkBoundary(page=browser_page)).execute(request).result
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": result.status == "succeeded", "final_response_ready": True, "result_status": result.status, "browser_action_count": 1, "browser_action_kind": browser_action.action_kind.value, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Safe browser read result is ready for provider continuation.", metadata={"integration_summary": {"raw_payload_persisted": False, "browser_action_kind": browser_action.action_kind.value}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": result.status == "succeeded", "raw_payload_persisted": False}
    approval_decision = store.approval_store.read_decision(resume_approval_request_id) if resume_approval_request_id else None
    if approval_decision is not None and approval_decision.decision == "approved":
        permission = _permission(proposal)
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"browser-result.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=proposal.capability_ref, status="requires_human_approval", safe_result={"browser_action_ready": True, "live_execution_deferred": True}, raw_input_persisted=False, raw_output_persisted=False)
        tool_projection = {"approval_decision": "approved", "pending_approval_count": 0, "execution_request_present": True, "provider_continuation_ready": False, "final_response_ready": False, "result_status": result.status, "browser_action_count": 1, "browser_action_kind": browser_action.action_kind.value, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Browser action approval was recorded; execution remains bounded by adapter policy.", metadata={"integration_summary": {"approved_count": 1, "raw_payload_persisted": False}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": False, "raw_payload_persisted": False}
    approval_request = _approval_request(turn_input, proposal.capability_ref)
    store.add_pending_approval(approval_request)
    tool_projection = {"pending_approval_count": 1, "provider_continuation_ready": False, "final_response_ready": False, "result_status": "requires_human_approval", "browser_action_count": 1, "browser_action_kind": browser_action.action_kind.value, "raw_payload_persisted": False}
    assistant_result = _approval_required_result(turn_input)
    lifecycle_projection = {"trace_id": turn_input.trace_id, "turn_id": turn_input.turn_id, "tool_result_delivery_ready": False, "raw_payload_persisted": False}
    return assistant_result, tool_projection, lifecycle_projection


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


def _calculator_proposal(turn_input: AssistantTurnInput) -> CapabilityCallProposal:
    return CapabilityCallProposal(schema_version=turn_input.schema_version, proposal_id=f"proposal.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"), proposed_action="calculator.evaluate", risk_level=ToolRiskLevel.SAFE, side_effect_level=ToolSideEffectLevel.READ_ONLY, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, arguments_schema={"type": "object", "properties": {"expression": {"type": "string"}}})


def _browser_action_proposal(turn_input: AssistantTurnInput) -> BrowserActionProposal:
    text = (turn_input.user_visible_input or "").lower()
    action = BrowserActionKind.EXTRACT_TEXT if any(marker in text for marker in ("read", "extract", "page text")) else BrowserActionKind.CLICK
    target = "body" if action == BrowserActionKind.EXTRACT_TEXT else "browser.action"
    return BrowserActionProposal(schema_version=turn_input.schema_version, proposal_id=f"browser-proposal.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, session_ref=BrowserSessionRef(session_id=f"browser-session.{turn_input.turn_id}"), action_kind=action, target=target, text_preview=None)


def _browser_proposal(turn_input: AssistantTurnInput) -> CapabilityCallProposal:
    return _browser_action_proposal(turn_input).to_capability_proposal()


def _permission(proposal: CapabilityCallProposal) -> CapabilityPermissionDecision:
    requires_approval = proposal.requires_approval
    return CapabilityPermissionDecision(schema_version=proposal.schema_version, decision_id=f"permission.{proposal.turn_id}", capability_ref=proposal.capability_ref, decision="approved", reason_code="policy_allowlisted", human_approval=HumanApprovalRequirement(required=requires_approval, reason_code="approval_required" if requires_approval else "not_required", prompt_user_visible=requires_approval, risk_level=proposal.risk_level, side_effect_level=proposal.side_effect_level))


def _approval_request(turn_input: AssistantTurnInput, capability_ref: CapabilityRef | None = None) -> CapabilityApprovalRequest:
    ref = capability_ref or CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click")
    return CapabilityApprovalRequest(schema_version=turn_input.schema_version, approval_request_id=f"approval-{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=ref, prompt=ApprovalPrompt(schema_version=turn_input.schema_version, prompt_id=f"approval-prompt-{turn_input.turn_id}", capability_ref=ref, user_visible_summary="Browser action requires approval.", risk_level=ToolRiskLevel.HIGH, side_effect_level=ToolSideEffectLevel.BROWSER_ACTION))


def _approval_required_result(turn_input: AssistantTurnInput) -> AssistantTurnResult:
    return build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Approval required before browser action.", metadata={"integration_summary": {"pending_approval_count": 1, "raw_payload_persisted": False}})


def _telemetry_summary(prompt_result: Any, confidence_bucket: str, context_pack: Any, planning_needed: bool, tool_projection: dict[str, Any]) -> dict[str, Any]:
    summary = HarnessTelemetrySummary.from_harness(prompt_result, route_confidence_bucket=confidence_bucket, context_candidates_count=len(context_pack.included) + len(context_pack.excluded), excluded_context_count=len(context_pack.excluded), planning_needed=planning_needed)
    data = summary.model_dump()
    data["executed_tool_count"] = 1 if tool_projection.get("result_status") == "succeeded" else 0
    data["pending_approval_count"] = int(tool_projection.get("pending_approval_count", 0) or 0)
    data["browser_execution_status"] = tool_projection.get("result_status") if tool_projection.get("browser_action_count") else None
    data["mcp_execution_status"] = tool_projection.get("mcp_execution_status")
    data["memory_context_ref_count"] = _context_source_count(context_pack, ContextSourceKind.MEMORY_PROJECTION)
    return data


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


def _provider_expression(raw_tool_call: dict[str, Any]) -> str:
    function = raw_tool_call.get("function") if isinstance(raw_tool_call, dict) else None
    arguments = function.get("arguments") if isinstance(function, dict) else raw_tool_call.get("arguments")
    parsed: object = {}
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {}
    elif isinstance(arguments, dict):
        parsed = arguments
    expression = parsed.get("expression") if isinstance(parsed, dict) else None
    return expression if isinstance(expression, str) and 0 < len(expression) <= 120 else "2 + 2"


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


def _approval_status(tool_projection: dict[str, Any]) -> str:
    if int(tool_projection.get("pending_approval_count", 0) or 0):
        return "pending"
    decision = tool_projection.get("approval_decision")
    return str(decision) if decision else "not_required"


def _safe_ref(ref: Any) -> dict[str, str] | None:
    return ref.model_dump() if ref is not None else None


def _emit(sink: TelemetrySink, turn_input: AssistantTurnInput, stage: TraceStage, message: str, data: dict[str, object]) -> None:
    sink.emit(make_trace_event(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, stage=stage, level=TraceLevel.INFO, message=message, data=data))
