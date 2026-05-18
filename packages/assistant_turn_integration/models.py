from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.contracts import AssistantTurnResult
from packages.context_runtime import SafeContextProjection
from packages.intent_runtime import SafeIntentProjection
from packages.prompt_harness_runtime import SafePromptProjection


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
