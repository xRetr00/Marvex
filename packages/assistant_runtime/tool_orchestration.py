from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from packages.capability_runtime import (
    AgentLoopDecision,
    AgentLoopState,
    AgentLoopStep,
    AgentLoopStopReason,
    CapabilityCallProposal,
    CapabilityPermissionDecision,
    CapabilityResultEnvelope,
    ToolContinuationState,
)
from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.contracts import AssistantTurnInput

from .lifecycle import AssistantTurnLifecycleSummary, build_turn_lifecycle_summary


class ToolOrchestratedTurnState(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    eligible_capability_count: int = Field(..., ge=0)
    provider_tool_proposal_count: int = Field(default=0, ge=0)
    loop_state: AgentLoopState
    proposal: CapabilityCallProposal | None = None
    permission_decision: CapabilityPermissionDecision | None = None
    result_envelope: CapabilityResultEnvelope | None = None
    continuation_state: ToolContinuationState | None = None
    provider_continuation_ready: bool = False
    final_response_ready: bool = False
    raw_payload_persisted: Literal[False] = False

    @classmethod
    def from_provider_proposal(
        cls,
        *,
        turn_input: AssistantTurnInput,
        eligible_capability_count: int,
        proposal: CapabilityCallProposal,
    ) -> ToolOrchestratedTurnState:
        _validate_turn_link(turn_input, proposal.trace_id, proposal.turn_id)
        loop_state = AgentLoopState(
            schema_version=turn_input.schema_version,
            loop_id=f"{turn_input.turn_id}:tool-loop",
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            max_steps=4,
            steps=(),
            proposed_tool_count=1,
        )
        return cls(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            eligible_capability_count=eligible_capability_count,
            provider_tool_proposal_count=1,
            loop_state=loop_state,
            proposal=proposal,
        )

    @classmethod
    def from_safe_result(
        cls,
        *,
        turn_input: AssistantTurnInput,
        eligible_capability_count: int,
        proposal: CapabilityCallProposal,
        permission_decision: CapabilityPermissionDecision,
        result: CapabilityResultEnvelope,
        continuation_id: str,
    ) -> ToolOrchestratedTurnState:
        _validate_turn_link(turn_input, proposal.trace_id, proposal.turn_id)
        if permission_decision.capability_ref != proposal.capability_ref:
            raise ValueError("permission decision must match provider tool proposal")
        if result.capability_ref != proposal.capability_ref:
            raise ValueError("tool result must match provider tool proposal")
        decision = AgentLoopDecision.from_proposal(
            decision_id=f"{proposal.proposal_id}:decision",
            proposal=proposal,
            permission_decision=permission_decision,
        )
        step = AgentLoopStep(
            schema_version=turn_input.schema_version,
            step_id=f"{proposal.proposal_id}:step",
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            step_index=1,
            decision=decision,
            result_envelope=result,
        )
        loop_state = AgentLoopState(
            schema_version=turn_input.schema_version,
            loop_id=f"{turn_input.turn_id}:tool-loop",
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            max_steps=4,
            steps=(step,),
            completed_steps=1,
            proposed_tool_count=1,
            approved_count=1,
            executed_count=1,
            stop_reason=AgentLoopStopReason.PROVIDER_CONTINUATION_READY,
        )
        continuation = ToolContinuationState.from_result(
            continuation_id=continuation_id,
            result=result,
            provider_continuation_ready=True,
        )
        return cls(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            eligible_capability_count=eligible_capability_count,
            provider_tool_proposal_count=1,
            loop_state=loop_state,
            proposal=proposal,
            permission_decision=permission_decision,
            result_envelope=result,
            continuation_state=continuation,
            provider_continuation_ready=True,
            final_response_ready=True,
        )

    @model_validator(mode="after")
    def _validate_state_links(self) -> ToolOrchestratedTurnState:
        for item in (self.proposal, self.result_envelope, self.continuation_state):
            if item is not None and (item.trace_id != self.trace_id or item.turn_id != self.turn_id):
                raise ValueError("tool-orchestrated turn linked items trace_id must match turn state")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "eligible_capability_count": self.eligible_capability_count,
            "provider_tool_proposal_count": self.provider_tool_proposal_count,
            "loop_step_count": len(self.loop_state.steps),
            "provider_continuation_ready": self.provider_continuation_ready,
            "final_response_ready": self.final_response_ready,
            "result_status": self.result_envelope.status if self.result_envelope else None,
            "raw_payload_persisted": False,
        }


def build_tool_orchestrated_lifecycle_summary(
    turn_input: AssistantTurnInput,
    state: ToolOrchestratedTurnState,
) -> AssistantTurnLifecycleSummary:
    _validate_turn_link(turn_input, state.trace_id, state.turn_id)
    summary = build_turn_lifecycle_summary(
        turn_input,
        capability_readiness_count=state.eligible_capability_count,
        selected_eligible_capability_count=state.loop_state.proposed_tool_count,
        denied_capability_count=state.loop_state.denied_count,
        executed_fake_capability_count=0,
        capability_safe_result_status=(state.result_envelope.status if state.result_envelope else None),
    )
    object.__setattr__(summary, "agent_loop_step_count", len(state.loop_state.steps))
    object.__setattr__(summary, "tool_result_delivery_ready", state.provider_continuation_ready)
    return summary


def _validate_turn_link(turn_input: AssistantTurnInput, trace_id: str, turn_id: str) -> None:
    if trace_id != turn_input.trace_id:
        raise ValueError("trace_id must match assistant turn input")
    if turn_id != turn_input.turn_id:
        raise ValueError("turn_id must match assistant turn input")
