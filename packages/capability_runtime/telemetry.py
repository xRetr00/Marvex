from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.capability_runtime.loop import AgentLoopState
from packages.capability_runtime.models import CapabilityRuntimeModel


class ToolingTelemetrySummary(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    tool_proposal_count: int = Field(..., ge=0)
    approved_count: int = Field(..., ge=0)
    denied_count: int = Field(..., ge=0)
    executed_tool_count: int = Field(..., ge=0)
    browser_action_count: int = Field(..., ge=0)
    computer_action_count: int = Field(..., ge=0)
    high_risk_pending_approval_count: int = Field(..., ge=0)
    raw_tool_payloads_persisted: Literal[False] = False
    raw_browser_payload_persisted: Literal[False] = False
    raw_screenshots_persisted: Literal[False] = False

    @classmethod
    def from_agent_loop_state(cls, state: AgentLoopState) -> ToolingTelemetrySummary:
        return cls(
            schema_version=state.schema_version,
            trace_id=state.trace_id,
            turn_id=state.turn_id,
            tool_proposal_count=state.proposed_tool_count,
            approved_count=state.approved_count,
            denied_count=state.denied_count,
            executed_tool_count=state.executed_count,
            browser_action_count=0,
            computer_action_count=0,
            high_risk_pending_approval_count=state.high_risk_pending_approval_count,
        )

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump()
