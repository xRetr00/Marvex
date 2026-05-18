from __future__ import annotations

import importlib.util
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.capability_runtime import (
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class BrowserUseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrowserUseAdapterConfig(BrowserUseModel):
    schema_version: str = Field(..., min_length=1)
    adapter_id: str = Field(..., min_length=1)
    backend_name: Literal["browser-use"] = "browser-use"
    backend_enabled: Literal[False] = False
    blocked_reason: str = Field(..., min_length=1)
    raw_browser_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "backend_name": self.backend_name,
            "backend_enabled": self.backend_enabled,
            "blocked_reason": self.blocked_reason,
            "raw_browser_payload_persisted": False,
        }


class BrowserUseBackendProbe(BrowserUseModel):
    backend_name: Literal["browser-use"] = "browser-use"
    package_importable: bool
    sdk_package_importable: bool
    execution_supported_without_approval: Literal[False] = False
    playwright_remains_low_level_backend: Literal[True] = True
    blocked_reason: str = Field(..., min_length=1)

    @classmethod
    def from_installed_backend(cls) -> "BrowserUseBackendProbe":
        return cls(
            package_importable=importlib.util.find_spec("browser_use") is not None,
            sdk_package_importable=importlib.util.find_spec("browser_use_sdk") is not None,
            blocked_reason="browser_use_backend_installed_but_execution_disabled_by_policy",
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "backend_name": self.backend_name,
            "package_importable": self.package_importable,
            "sdk_package_importable": self.sdk_package_importable,
            "execution_supported_without_approval": False,
            "playwright_remains_low_level_backend": True,
            "blocked_reason": self.blocked_reason,
        }


class BrowserUseTaskProposal(BrowserUseModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    task_summary: str = Field(..., min_length=1, max_length=500)
    risk_level: ToolRiskLevel = ToolRiskLevel.HIGH
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.BROWSER_ACTION
    requires_approval: Literal[True] = True
    backend_execution_enabled: Literal[False] = False

    def to_capability_proposal(self):
        from packages.capability_runtime import CapabilityCallProposal

        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser_use.task"),
            proposed_action="browser_use_task",
            risk_level=self.risk_level,
            side_effect_level=self.side_effect_level,
            execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )


class BrowserUseExecutionRequest(BrowserUseModel):
    proposal: BrowserUseTaskProposal
    execution_request: CapabilityExecutionRequest
    backend_execution_enabled: Literal[False] = False

    @classmethod
    def from_proposal(
        cls,
        *,
        request_id: str,
        proposal: BrowserUseTaskProposal,
        permission_decision: CapabilityPermissionDecision,
    ) -> BrowserUseExecutionRequest:
        safe_proposal = proposal.to_capability_proposal().model_copy(update={
            "risk_level": ToolRiskLevel.MEDIUM,
            "side_effect_level": ToolSideEffectLevel.READ_ONLY,
            "execution_mode": CapabilityExecutionMode.APPROVED_EXECUTE,
        })
        return cls(
            proposal=proposal,
            execution_request=CapabilityExecutionRequest(
                schema_version=proposal.schema_version,
                request_id=request_id,
                trace_id=proposal.trace_id,
                turn_id=proposal.turn_id,
                proposal=safe_proposal,
                permission_decision=permission_decision,
                arguments={"task_summary_present": True},
                approval_decision=None,
                execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
            ),
        )

    @model_validator(mode="after")
    def _disabled_backend(self) -> BrowserUseExecutionRequest:
        object.__setattr__(self, "backend_execution_enabled", False)
        return self

    def safe_result_envelope(self, *, result_id: str) -> CapabilityResultEnvelope:
        return CapabilityResultEnvelope(
            schema_version=self.proposal.schema_version,
            result_id=result_id,
            trace_id=self.proposal.trace_id,
            turn_id=self.proposal.turn_id,
            capability_ref=self.proposal.to_capability_proposal().capability_ref,
            status="denied",
            safe_result={"backend_enabled": False, "blocked_reason": "browser_use_backend_disabled"},
            raw_input_persisted=False,
            raw_output_persisted=False,
        )
