from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionMode,
    CapabilityKind,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class ComputerUseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ComputerUseHarnessConfig(ComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    adapter_id: str = Field(..., min_length=1)
    backend: str = Field(..., min_length=1)
    isolated_environment_required: Literal[True] = True
    screen_content_untrusted: Literal[True] = True
    credential_entry_allowed: Literal[False] = False
    arbitrary_desktop_control_allowed: Literal[False] = False
    raw_screen_persisted: Literal[False] = False

    @classmethod
    def from_openai(cls, config) -> ComputerUseHarnessConfig:
        return cls(
            schema_version=config.schema_version,
            adapter_id=config.adapter_id,
            backend="openai_computer_use",
            isolated_environment_required=config.isolated_environment_required,
            screen_content_untrusted=config.screen_content_untrusted,
        )


class ComputerUseTaskProposal(ComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    task_summary: str = Field(..., min_length=1, max_length=500)
    harness_config: ComputerUseHarnessConfig


class ComputerUseActionProposal(ComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    action_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    task_proposal_id: str = Field(..., min_length=1)
    action_summary: str = Field(..., min_length=1, max_length=500)
    harness_config: ComputerUseHarnessConfig
    risk_level: ToolRiskLevel = ToolRiskLevel.HIGH
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.DESKTOP_ACTION
    requires_approval: Literal[True] = True

    @classmethod
    def from_task(
        cls,
        task: ComputerUseTaskProposal,
        *,
        action_id: str,
        action_summary: str,
    ) -> ComputerUseActionProposal:
        return cls(
            schema_version=task.schema_version,
            action_id=action_id,
            trace_id=task.trace_id,
            turn_id=task.turn_id,
            task_proposal_id=task.proposal_id,
            action_summary=action_summary,
            harness_config=task.harness_config,
        )

    def to_capability_proposal(self):
        from packages.capability_runtime import CapabilityCallProposal

        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.action_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="computer_use.action"),
            proposed_action="computer_use_action",
            risk_level=self.risk_level,
            side_effect_level=self.side_effect_level,
            execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )


class ComputerUseResultEnvelope(ComputerUseModel):
    result: CapabilityResultEnvelope
    raw_screen_persisted: Literal[False] = False
    raw_action_payload_persisted: Literal[False] = False

    @classmethod
    def from_proposal(
        cls,
        proposal: ComputerUseActionProposal,
        *,
        result_id: str,
        status: Literal["succeeded", "failed", "denied", "requires_human_approval"],
        safe_result: dict[str, object],
    ) -> ComputerUseResultEnvelope:
        return cls(
            result=CapabilityResultEnvelope(
                schema_version=proposal.schema_version,
                result_id=result_id,
                trace_id=proposal.trace_id,
                turn_id=proposal.turn_id,
                capability_ref=proposal.to_capability_proposal().capability_ref,
                status=status,
                safe_result=safe_result,
                raw_input_persisted=False,
                raw_output_persisted=False,
            )
        )
