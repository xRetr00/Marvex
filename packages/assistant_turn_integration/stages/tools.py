from __future__ import annotations

import asyncio
import json
from typing import Any

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
from packages.contracts import AssistantTurnInput, AssistantTurnResult
from packages.telemetry import TelemetrySink

from packages.assistant_turn_integration.state import EndToEndTurnStateStore


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


def _handle_provider_tool_call_turn(turn_input: AssistantTurnInput, *, model: str, instructions: str | None, previous_response_id: str | None, telemetry_sink: TelemetrySink, raw_tool_call: dict[str, Any], source: ProviderToolCallSource, memory_tree_evidence_ref_count: int = 0, provider_continuation_provider: Any | None = None) -> tuple[AssistantTurnResult, dict[str, Any], dict[str, Any]]:
    mapper = ProviderToolCallMapper(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id)
    mapped = mapper.from_litellm(raw_tool_call) if source is ProviderToolCallSource.LITELLM else mapper.from_openai_compatible(raw_tool_call, source=source)
    provider_proposal = mapped.to_capability_proposal()
    tool_name_status = str(getattr(mapped, "tool_name_status", "safe"))
    if tool_name_status == "unsafe":
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"provider-tool-denied.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=provider_proposal.capability_ref, status="denied", safe_result={"reason_code": "unsafe_provider_tool_name"}, raw_input_persisted=False, raw_output_persisted=False)
        continuation_input = _provider_continuation_input(provider_proposal.proposal_id, result, memory_tree_evidence_ref_count=memory_tree_evidence_ref_count)
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": True, "provider_continuation_input_ready": True, "provider_continuation_input": continuation_input, "provider_final_response_status": "completed", "final_response_ready": True, "result_status": result.status, "provider_tool_name_status": "unsafe", "safe_result_reason_code": "unsafe_provider_tool_name", "provider_tool_call_source": source.value, "provider_tool_proposal_id": provider_proposal.proposal_id, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Provider tool proposal name was rejected by Marvex policy.", metadata={"integration_summary": {"raw_payload_persisted": False}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": True, "provider_continuation_input_ready": True, "raw_payload_persisted": False}
    if provider_proposal.proposed_action != "calculator":
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"provider-tool-denied.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=provider_proposal.capability_ref, status="denied", safe_result={"reason_code": "unsupported_provider_tool"}, raw_input_persisted=False, raw_output_persisted=False)
        continuation_input = _provider_continuation_input(provider_proposal.proposal_id, result, memory_tree_evidence_ref_count=memory_tree_evidence_ref_count)
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": True, "provider_continuation_input_ready": True, "provider_continuation_input": continuation_input, "provider_final_response_status": "completed", "final_response_ready": True, "result_status": result.status, "safe_result_reason_code": "unsupported_provider_tool", "provider_tool_call_source": source.value, "provider_tool_proposal_id": provider_proposal.proposal_id, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Provider tool proposal was denied by Marvex policy.", metadata={"integration_summary": {"raw_payload_persisted": False}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": True, "provider_continuation_input_ready": True, "raw_payload_persisted": False}
    expression, argument_status, reason_code = _provider_expression(raw_tool_call)
    if expression is None:
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"provider-tool-denied.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=provider_proposal.capability_ref, status="denied", safe_result={"reason_code": reason_code or "invalid_provider_tool_arguments"}, raw_input_persisted=False, raw_output_persisted=False)
        continuation_input = _provider_continuation_input(provider_proposal.proposal_id, result, memory_tree_evidence_ref_count=memory_tree_evidence_ref_count)
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": True, "provider_continuation_input_ready": True, "provider_continuation_input": continuation_input, "provider_final_response_status": "completed", "final_response_ready": True, "result_status": result.status, "provider_tool_argument_status": argument_status, "safe_result_reason_code": result.safe_result["reason_code"], "provider_tool_call_source": source.value, "provider_tool_proposal_id": provider_proposal.proposal_id, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Provider tool proposal arguments were rejected by Marvex policy.", metadata={"integration_summary": {"raw_payload_persisted": False, "provider_tool_call_source": source.value}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": True, "provider_continuation_input_ready": True, "raw_payload_persisted": False}
    proposal = _calculator_proposal(turn_input)
    permission = _permission(proposal)
    execution_request = CapabilityExecutionRequest(schema_version=turn_input.schema_version, request_id=f"provider-tool-request.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, proposal=proposal, permission_decision=permission, arguments={"expression": expression})
    try:
        result = BuiltinToolCatalog.default().execute_request(execution_request).result
    except Exception:
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"provider-tool-failed.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=proposal.capability_ref, status="denied", safe_result={"reason_code": "invalid_calculator_expression"}, raw_input_persisted=False, raw_output_persisted=False)
    state = ToolOrchestratedTurnState.from_safe_result(turn_input=turn_input, eligible_capability_count=1, proposal=proposal, permission_decision=permission, result=result, continuation_id=f"provider-tool-continuation.{turn_input.turn_id}")
    lifecycle = build_tool_orchestrated_lifecycle_summary(turn_input, state)
    continuation_input = _provider_continuation_input(provider_proposal.proposal_id, result, memory_tree_evidence_ref_count=memory_tree_evidence_ref_count)
    final_text = _provider_final_text(result)
    continuation_backend = "provider_port" if provider_continuation_provider is not None else "fake_provider_proof"
    continuation_provider = provider_continuation_provider or FakeProvider(FakeProviderConfig(output_text=final_text))
    provider_options = {"tool_continuation_ready": True, "provider_continuation_input": continuation_input, "provider_continuation_backend": continuation_backend, "raw_tool_output_persisted": False, "raw_provider_payload_persisted": False}
    provider_result = run_provider_stage_turn(turn_input, provider=continuation_provider, model=model, instructions=instructions, previous_response_id=previous_response_id, provider_options=provider_options, telemetry_sink=telemetry_sink)
    projection = state.safe_projection()
    projection["provider_tool_call_source"] = source.value
    projection["provider_tool_proposal_id"] = provider_proposal.proposal_id
    projection["provider_tool_capability_ref"] = provider_proposal.capability_ref.identifier
    projection["provider_tool_argument_status"] = argument_status
    projection["provider_tool_name_status"] = tool_name_status
    projection["provider_continuation_backend"] = continuation_backend
    projection["provider_continuation_input_ready"] = True
    projection["provider_continuation_input"] = continuation_input
    projection["provider_final_response_status"] = "completed" if provider_result.assistant_final_response is not None else "failed"
    assistant_result = provider_result.model_copy(update={"metadata": {"integration_summary": {"raw_payload_persisted": False, "provider_tool_call_source": source.value, "provider_continuation_input_ready": True, "provider_continuation_backend": continuation_backend}}})
    lifecycle_projection = lifecycle.safe_projection()
    lifecycle_projection["provider_continuation_input_ready"] = True
    return assistant_result, projection, lifecycle_projection


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
        tool_projection = {"pending_approval_count": 0, "provider_continuation_ready": result.status == "succeeded", "provider_continuation_input_ready": result.status == "succeeded", "final_response_ready": True, "result_status": result.status, "browser_action_count": 1, "browser_action_kind": browser_action.action_kind.value, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Safe browser read result is ready for provider continuation.", metadata={"integration_summary": {"raw_payload_persisted": False, "browser_action_kind": browser_action.action_kind.value}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": result.status == "succeeded", "provider_continuation_input_ready": result.status == "succeeded", "raw_payload_persisted": False}
    approval_decision = store.approval_store.read_decision(resume_approval_request_id) if resume_approval_request_id else None
    if approval_decision is not None and approval_decision.decision == "denied":
        outcome = "cancelled" if approval_decision.decision_id.endswith(":cancelled") else "denied"
        result = CapabilityResultEnvelope(schema_version=turn_input.schema_version, result_id=f"browser-result.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=proposal.capability_ref, status="denied", safe_result={"approval_decision": outcome}, raw_input_persisted=False, raw_output_persisted=False)
        tool_projection = {"approval_decision": outcome, "pending_approval_count": 0, "execution_request_present": False, "provider_continuation_ready": True, "provider_continuation_input_ready": True, "final_response_ready": True, "result_status": result.status, "browser_action_count": 1, "browser_action_kind": browser_action.action_kind.value, "raw_payload_persisted": False}
        assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text=f"Browser action was {outcome}.", metadata={"integration_summary": {"approval_decision": outcome, "raw_payload_persisted": False}})
        return assistant_result, tool_projection, {"tool_result_delivery_ready": True, "provider_continuation_input_ready": True, "raw_payload_persisted": False}
    if approval_decision is not None and approval_decision.decision == "approved":
        permission = _permission(proposal)
        if browser_page is not None:
            request = BrowserExecutionRequest.from_proposal(request_id=f"browser-request.{turn_input.turn_id}", proposal=browser_action, permission_decision=permission, approval_decision=approval_decision)
            result = PlaywrightBrowserWorkflow(boundary=PlaywrightSdkBoundary(page=browser_page)).execute(request).result
            tool_projection = {"approval_decision": "approved", "pending_approval_count": 0, "execution_request_present": True, "provider_continuation_ready": result.status == "succeeded", "provider_continuation_input_ready": result.status == "succeeded", "final_response_ready": True, "result_status": result.status, "browser_action_count": 1, "browser_action_kind": browser_action.action_kind.value, "raw_payload_persisted": False}
            assistant_result = build_text_success_turn_result(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, text="Approved browser action result is ready for provider continuation.", metadata={"integration_summary": {"approved_count": 1, "raw_payload_persisted": False}})
            return assistant_result, tool_projection, {"tool_result_delivery_ready": result.status == "succeeded", "provider_continuation_input_ready": result.status == "succeeded", "raw_payload_persisted": False}
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


def _calculator_proposal(turn_input: AssistantTurnInput) -> CapabilityCallProposal:
    return CapabilityCallProposal(schema_version=turn_input.schema_version, proposal_id=f"proposal.{turn_input.turn_id}", trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator"), proposed_action="calculator.evaluate", risk_level=ToolRiskLevel.SAFE, side_effect_level=ToolSideEffectLevel.READ_ONLY, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, arguments_schema={"type": "object", "properties": {"expression": {"type": "string"}}})


def _browser_action_proposal(turn_input: AssistantTurnInput) -> BrowserActionProposal:
    text = (turn_input.user_visible_input or "").lower()
    if any(marker in text for marker in ("read", "extract", "page text")):
        action = BrowserActionKind.EXTRACT_TEXT
        target = "body"
    elif any(marker in text for marker in ("navigate", "go to", "open")):
        action = BrowserActionKind.NAVIGATE
        target = _browser_navigation_target(turn_input.user_visible_input or "")
    else:
        action = BrowserActionKind.CLICK
        target = "browser.action"
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


def _provider_continuation_input(provider_tool_call_id: str, result: CapabilityResultEnvelope, *, memory_tree_evidence_ref_count: int = 0) -> dict[str, object]:
    return {
        "tool_call_id": provider_tool_call_id,
        "capability_ref": result.capability_ref.safe_projection(),
        "result_status": result.status,
        "safe_result_keys": tuple(sorted(result.safe_result)),
        "memory_tree_evidence_ref_count": memory_tree_evidence_ref_count,
        "raw_tool_output_persisted": False,
        "raw_provider_payload_persisted": False,
    }


def _provider_final_text(result: CapabilityResultEnvelope) -> str:
    if result.status == "succeeded" and "result" in result.safe_result:
        return f"The calculator result is {result.safe_result['result']}."
    if result.status == "denied":
        return "The provider tool result was denied by Marvex policy."
    return "The provider tool result is ready for continuation."


def _provider_expression(raw_tool_call: dict[str, Any]) -> tuple[str | None, str, str | None]:
    function = raw_tool_call.get("function") if isinstance(raw_tool_call, dict) else None
    arguments = function.get("arguments") if isinstance(function, dict) else raw_tool_call.get("arguments")
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return None, "malformed", "malformed_provider_tool_arguments"
    elif isinstance(arguments, dict):
        parsed = arguments
    else:
        return None, "invalid", "invalid_provider_tool_arguments"
    if not isinstance(parsed, dict):
        return None, "invalid", "invalid_provider_tool_arguments"
    expression = parsed.get("expression") if isinstance(parsed, dict) else None
    if not isinstance(expression, str):
        return None, "invalid", "invalid_provider_tool_arguments"
    normalized = expression.strip()
    if not normalized or len(normalized) > 120:
        return None, "invalid", "invalid_provider_tool_arguments"
    if any(marker in normalized.lower() for marker in ("secret", "token", "password", "credential", "bearer")):
        return None, "invalid", "unsafe_provider_tool_arguments"
    return normalized, "valid", None


def _browser_navigation_target(text: str) -> str:
    for marker in ("https://", "http://"):
        start = text.find(marker)
        if start < 0:
            continue
        end = start
        while end < len(text) and not text[end].isspace() and text[end] not in ")]}>'\"":
            end += 1
        return text[start:end][:500]
    return "about:blank"
