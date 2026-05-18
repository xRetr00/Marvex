from __future__ import annotations

from enum import Enum
from typing import Literal

from playwright.sync_api import Browser, BrowserContext, Page
from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.capability_runtime import (
    ApprovalDecision,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class BrowserAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class BrowserActionKind(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    READ_PAGE = "read_page"
    SCREENSHOT = "screenshot"
    EXTRACT_TEXT = "extract_text"


class BrowserSessionRef(BrowserAdapterModel):
    session_id: str = Field(..., min_length=1)
    isolated: Literal[True] = True
    credentials_available: Literal[False] = False


class PlaywrightBrowserAdapterConfig(BrowserAdapterModel):
    schema_version: str = Field(..., min_length=1)
    adapter_id: str = Field(..., min_length=1)
    backend: Literal["playwright"] = "playwright"
    headless: bool
    isolated_session_required: Literal[True] = True
    raw_dom_persisted: Literal[False] = False
    raw_screenshot_persisted: Literal[False] = False


class BrowserActionProposal(BrowserAdapterModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    session_ref: BrowserSessionRef
    action_kind: BrowserActionKind
    target: str = Field(..., min_length=1, max_length=500)
    text_preview: str | None = Field(default=None, max_length=120)
    submit_sensitive_data: Literal[False] = False
    captcha_or_antibot_bypass_allowed: Literal[False] = False

    @property
    def risk_level(self) -> ToolRiskLevel:
        if self.action_kind in {BrowserActionKind.CLICK, BrowserActionKind.TYPE, BrowserActionKind.NAVIGATE}:
            return ToolRiskLevel.HIGH
        return ToolRiskLevel.LOW

    @property
    def side_effect_level(self) -> ToolSideEffectLevel:
        if self.action_kind in {BrowserActionKind.CLICK, BrowserActionKind.TYPE, BrowserActionKind.NAVIGATE}:
            return ToolSideEffectLevel.BROWSER_ACTION
        return ToolSideEffectLevel.READ_ONLY

    @property
    def requires_approval(self) -> bool:
        return self.side_effect_level == ToolSideEffectLevel.BROWSER_ACTION

    def to_capability_proposal(self):
        from packages.capability_runtime import CapabilityCallProposal

        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.proposal_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier=f"browser.{self.action_kind.value}"),
            proposed_action=self.action_kind.value,
            risk_level=self.risk_level,
            side_effect_level=self.side_effect_level,
            execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL if self.requires_approval else CapabilityExecutionMode.PROPOSAL_ONLY,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )


class BrowserExecutionRequest(BrowserAdapterModel):
    browser_proposal: BrowserActionProposal
    execution_request: CapabilityExecutionRequest
    sdk_backend: Literal["playwright"] = "playwright"
    raw_browser_payload_persisted: Literal[False] = False

    @classmethod
    def from_proposal(
        cls,
        *,
        request_id: str,
        proposal: BrowserActionProposal,
        permission_decision: CapabilityPermissionDecision,
        approval_decision: ApprovalDecision | None = None,
    ) -> BrowserExecutionRequest:
        capability_proposal = proposal.to_capability_proposal()
        return cls(
            browser_proposal=proposal,
            execution_request=CapabilityExecutionRequest(
                schema_version=proposal.schema_version,
                request_id=request_id,
                trace_id=proposal.trace_id,
                turn_id=proposal.turn_id,
                proposal=capability_proposal,
                permission_decision=permission_decision,
                approval_decision=approval_decision,
                arguments={"target": proposal.target, "text_preview_present": proposal.text_preview is not None},
                execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
                raw_arguments_persisted=False,
            ),
        )


class BrowserResultEnvelope(BrowserAdapterModel):
    result: CapabilityResultEnvelope
    action_kind: BrowserActionKind
    raw_dom_persisted: Literal[False] = False
    raw_page_text_persisted: Literal[False] = False
    raw_screenshot_persisted: Literal[False] = False

    @classmethod
    def from_execution(
        cls,
        request: BrowserExecutionRequest,
        *,
        result_id: str,
        status: Literal["succeeded", "failed", "denied", "requires_human_approval"],
        safe_result: dict[str, object],
    ) -> BrowserResultEnvelope:
        return cls(
            result=CapabilityResultEnvelope(
                schema_version=request.execution_request.schema_version,
                result_id=result_id,
                trace_id=request.execution_request.trace_id,
                turn_id=request.execution_request.turn_id,
                capability_ref=request.execution_request.proposal.capability_ref,
                status=status,
                safe_result=safe_result,
                raw_input_persisted=False,
                raw_output_persisted=False,
            ),
            action_kind=request.browser_proposal.action_kind,
        )


class PlaywrightSdkBoundary(BrowserAdapterModel):
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None

    @model_validator(mode="after")
    def _boundary_marker(self) -> PlaywrightSdkBoundary:
        return self
