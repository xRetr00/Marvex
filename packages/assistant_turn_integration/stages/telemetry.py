from __future__ import annotations

from typing import Any

from packages.contracts import AssistantTurnInput, TraceLevel, TraceStage
from packages.context_runtime import ContextSourceKind
from packages.prompt_harness_runtime import HarnessTelemetrySummary
from packages.telemetry import TelemetrySink, make_trace_event

from packages.assistant_turn_integration.stages.context import _context_source_count, _memory_tree_evidence_ref_count


def _telemetry_summary(prompt_result: Any, confidence_bucket: str, context_pack: Any, planning_needed: bool, tool_projection: dict[str, Any]) -> dict[str, Any]:
    summary = HarnessTelemetrySummary.from_harness(prompt_result, route_confidence_bucket=confidence_bucket, context_candidates_count=len(context_pack.included) + len(context_pack.excluded), excluded_context_count=len(context_pack.excluded), planning_needed=planning_needed)
    data = summary.model_dump()
    data["executed_tool_count"] = 1 if tool_projection.get("result_status") == "succeeded" else 0
    data["pending_approval_count"] = int(tool_projection.get("pending_approval_count", 0) or 0)
    data["browser_execution_status"] = tool_projection.get("result_status") if tool_projection.get("browser_action_count") else None
    data["mcp_execution_status"] = tool_projection.get("mcp_execution_status")
    data["memory_context_ref_count"] = _context_source_count(context_pack, ContextSourceKind.MEMORY_PROJECTION)
    data["memory_tree_evidence_ref_count"] = _memory_tree_evidence_ref_count(context_pack)
    data["memory_tree_context_included"] = data["memory_tree_evidence_ref_count"] > 0
    data["provider_continuation_status"] = "ready" if tool_projection.get("provider_continuation_ready") else "not_ready"
    data["provider_tool_proposal_count"] = 1 if tool_projection.get("provider_tool_proposal_id") else 0
    data["provider_continuation_input_ready"] = bool(tool_projection.get("provider_continuation_input_ready", False))
    data["provider_final_response_status"] = tool_projection.get("provider_final_response_status")
    data["approval_state"] = _approval_status(tool_projection)
    data["raw_tool_output_persisted"] = False
    data["raw_provider_payload_persisted"] = False
    return data


def _approval_status(tool_projection: dict[str, Any]) -> str:
    if int(tool_projection.get("pending_approval_count", 0) or 0):
        return "pending"
    decision = tool_projection.get("approval_decision")
    return str(decision) if decision else "not_required"


def _safe_ref(ref: Any) -> dict[str, str] | None:
    return ref.model_dump() if ref is not None else None


def _emit(sink: TelemetrySink, turn_input: AssistantTurnInput, stage: TraceStage, message: str, data: dict[str, object]) -> None:
    sink.emit(make_trace_event(schema_version=turn_input.schema_version, trace_id=turn_input.trace_id, turn_id=turn_input.turn_id, stage=stage, level=TraceLevel.INFO, message=message, data=data))
