from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field

from packages.adapters.capabilities.builtins import BuiltinToolCatalog
from packages.adapters.providers.fake.fake_provider import FakeProvider, FakeProviderConfig
from packages.assistant_runtime import build_tool_orchestrated_lifecycle_summary
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
from packages.intent_runtime import IntentKind, SafeIntentProjection, classify_intent, IntentClassificationRequest
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

    def add_pending_approval(self, request: CapabilityApprovalRequest) -> None:
        self.approval_store.add_pending(request)

    def record_result(self, result: EndToEndAssistantTurnResult) -> None:
        self.last_result = result

    def control_plane_snapshot(self) -> ControlPlaneSnapshot:
        if self.last_result is None:
            return ControlPlaneSnapshot.foundation_default(schema_version="1")
        trace = self.trace_reader.read_trace(self.last_result.trace_id)
        projection = self.last_result.safe_projection()
        return ControlPlaneSnapshot.foundation_default(
            schema_version="1",
            providers=({"provider_id": "fake", "configured": True, "secret_present": False},),
            capabilities=({"identifier": "builtin.calculator", "kind": "tool", "risk_level": "safe"},),
            tools=({"tool_id": "builtin.calculator", "side_effect_level": "read_only"},),
            traces=({"trace_id": self.last_result.trace_id, "event_count": (trace or {}).get("event_count", 0), "raw_payload_persisted": False},),
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
) -> EndToEndAssistantTurnResult:
    store = state_store or EndToEndTurnStateStore()
    telemetry_sink: TelemetrySink = store.trace_reader
    conversation_ref = ConversationRef(ref_type="conversation", ref_id=f"conversation.{turn_input.turn_id}")
    linkage = build_turn_linkage_from_assistant_turn_input(turn_input, conversation_ref=conversation_ref, previous_response_id=previous_response_id)
    _emit(telemetry_sink, turn_input, TraceStage.TURN_RECEIVED, "Integrated assistant turn received.", {"status": "received", "session_ref": _safe_ref(turn_input.session_ref), "conversation_ref": _safe_ref(conversation_ref)})

    intent = classify_intent(IntentClassificationRequest(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, user_input_summary=_input_summary(turn_input)))
    context_pack = _build_context(turn_input, intent.selected_intent)
    prompt_result = assemble_prompt_harness(PromptAssemblyRequest(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, intent_ref=intent.selected_intent, context_pack=context_pack))
    planning = PlanningNeedDecision.from_intent(intent.selected_intent, context_candidate_count=len(context_pack.included) + len(context_pack.excluded))

    if intent.selected_intent.intent_kind == IntentKind.BROWSER_COMPUTER_USE:
        approval_request = _approval_request(turn_input)
        store.add_pending_approval(approval_request)
        tool_projection = {"pending_approval_count": 1, "provider_continuation_ready": False, "final_response_ready": False, "result_status": "requires_human_approval", "raw_payload_persisted": False}
        assistant_result = _approval_required_result(turn_input)
        lifecycle_projection = {"trace_id": turn_input.trace_id, "turn_id": turn_input.turn_id, "tool_result_delivery_ready": False, "raw_payload_persisted": False}
        telemetry_summary = _telemetry_summary(prompt_result, intent.confidence.bucket.value, context_pack, planning.planning_needed, tool_projection)
        _emit(telemetry_sink, turn_input, TraceStage.TURN_COMPLETED, "Integrated assistant turn paused for approval.", {"status": "requires_human_approval"})
    else:
        proposal = _calculator_proposal(turn_input)
        permission = _permission(proposal)
        execution_request = CapabilityExecutionRequest(schema_version=turn_input.schema_version, request_id=f"request.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, proposal=proposal, permission_decision=permission, arguments={"expression": "2 + 2"})
        result = BuiltinToolCatalog.default().execute_request(execution_request).result
        state = ToolOrchestratedTurnState.from_safe_result(turn_input=turn_input, eligible_capability_count=1, proposal=proposal, permission_decision=permission, result=result, continuation_id=f"continuation.{turn_input.turn_id}")
        lifecycle = build_tool_orchestrated_lifecycle_summary(turn_input, state)
        provider_result = run_provider_stage_turn(
            turn_input,
            provider=FakeProvider(FakeProviderConfig(output_text="The calculator result is 4.")),
            model=model,
            instructions=instructions,
            previous_response_id=previous_response_id,
            provider_options={},
            telemetry_sink=telemetry_sink,
        )
        tool_projection = state.safe_projection()
        lifecycle_projection = lifecycle.safe_projection()
        telemetry_summary = _telemetry_summary(prompt_result, intent.confidence.bucket.value, context_pack, planning.planning_needed, tool_projection)
        assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "prompt_section_count": prompt_result.safe_projection().section_count, "context_included_count": context_pack.safe_projection().included_count}}})
        _emit(telemetry_sink, turn_input, TraceStage.TURN_COMPLETED, "Integrated assistant turn completed.", {"status": "success"})

    trace = store.trace_reader.read_trace(turn_input.trace_id)
    control_summary = {"telemetry_event_count": (trace or {}).get("event_count", 0), "pending_approval_count": store.approval_store.list_pending().pending_count, "raw_payload_persisted": False}
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


def _build_context(turn_input: AssistantTurnInput, intent_ref: Any) -> Any:
    eligibility = CapabilityEligibilityDecision(schema_version=turn_input.schema_version, decision_id=f"eligibility.{turn_input.turn_id}", capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"), eligible=True, reason_code="eligible.intent_selected", intent_tags=(IntentKind.CAPABILITY_TOOL.value,))
    candidates = (
        ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier=f"input.{turn_input.turn_id}"), _input_summary(turn_input), token_estimate=8, intent_tags=(intent_ref.intent_kind.value,), trust_level=ContextSourceTrustLevel.USER_SUMMARY),
        ContextCandidate.from_capability_schema(eligibility, token_estimate=8),
    )
    return build_context_pack(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, intent_ref=intent_ref, candidates=candidates, budget=ContextBudget(max_context_tokens=80, reserved_response_tokens=40), policy=ContextDeliveryPolicy(max_candidates=4, allowed_source_kinds=(ContextSourceKind.USER_INPUT_SUMMARY, ContextSourceKind.CAPABILITY_SCHEMA), include_excluded_reasons=True))


def _calculator_proposal(turn_input: AssistantTurnInput) -> CapabilityCallProposal:
    return CapabilityCallProposal(schema_version=turn_input.schema_version, proposal_id=f"proposal.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"), proposed_action="calculator.evaluate", risk_level=ToolRiskLevel.SAFE, side_effect_level=ToolSideEffectLevel.READ_ONLY, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, arguments_schema={"type": "object", "properties": {"expression": {"type": "string"}}})


def _permission(proposal: CapabilityCallProposal) -> CapabilityPermissionDecision:
    return CapabilityPermissionDecision(schema_version=proposal.schema_version, decision_id=f"permission.{proposal.turn_id}", capability_ref=proposal.capability_ref, decision="approved", reason_code="policy_allowlisted", human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False))


def _approval_request(turn_input: AssistantTurnInput) -> CapabilityApprovalRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click")
    return CapabilityApprovalRequest(schema_version=turn_input.schema_version, approval_request_id=f"approval-{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=ref, prompt=ApprovalPrompt(schema_version=turn_input.schema_version, prompt_id=f"approval-prompt-{turn_input.turn_id}", capability_ref=ref, user_visible_summary="Browser action requires approval.", risk_level=ToolRiskLevel.HIGH, side_effect_level=ToolSideEffectLevel.BROWSER_ACTION))


def _approval_required_result(turn_input: AssistantTurnInput) -> AssistantTurnResult:
    from packages.assistant_runtime import build_text_success_turn_result

    return build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Approval required before browser action.", metadata={"integration_summary": {"pending_approval_count": 1, "raw_payload_persisted": False}})


def _telemetry_summary(prompt_result: Any, confidence_bucket: str, context_pack: Any, planning_needed: bool, tool_projection: dict[str, Any]) -> dict[str, Any]:
    summary = HarnessTelemetrySummary.from_harness(prompt_result, route_confidence_bucket=confidence_bucket, context_candidates_count=len(context_pack.included) + len(context_pack.excluded), excluded_context_count=len(context_pack.excluded), planning_needed=planning_needed)
    data = summary.model_dump()
    data["executed_tool_count"] = 1 if tool_projection.get("result_status") == "succeeded" else 0
    data["pending_approval_count"] = int(tool_projection.get("pending_approval_count", 0) or 0)
    return data


def _input_summary(turn_input: AssistantTurnInput) -> str:
    text = (turn_input.user_visible_input or "").lower()
    if "click" in text or "browser" in text or "checkout" in text:
        return "User requested a browser action."
    if "calculator" in text or "2+2" in text or "calculate" in text:
        return "User requested a safe calculator capability."
    return "User requested a simple assistant response."


def _safe_ref(ref: Any) -> dict[str, str] | None:
    return ref.model_dump() if ref is not None else None


def _emit(sink: TelemetrySink, turn_input: AssistantTurnInput, stage: TraceStage, message: str, data: dict[str, object]) -> None:
    sink.emit(make_trace_event(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, stage=stage, level=TraceLevel.INFO, message=message, data=data))
