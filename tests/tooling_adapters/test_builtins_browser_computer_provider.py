from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from packages.adapters.capabilities.browser import (
    BrowserActionKind,
    BrowserActionProposal,
    BrowserExecutionRequest,
    BrowserResultEnvelope,
    BrowserSessionRef,
    PlaywrightBrowserAdapterConfig,
)
from packages.adapters.capabilities.browser_use import (
    BrowserUseAdapterConfig,
    BrowserUseBackendProbe,
    BrowserUseExecutionRequest,
    BrowserUseTaskProposal,
)
from packages.adapters.capabilities.builtins import (
    BuiltinToolCatalog,
    CalculatorRequest,
    RepoStatusSnapshot,
    TimeDateRequest,
)
from packages.adapters.capabilities.computer_use import (
    ComputerUseActionProposal,
    ComputerUseHarnessConfig,
    ComputerUseResultEnvelope,
    ComputerUseTaskProposal,
)
from packages.adapters.capabilities.litellm_gateway import LiteLLMToolCallProposal, LiteLLMToolsetRef
from packages.adapters.capabilities.lmstudio import LMStudioLocalToolProposal
from packages.adapters.capabilities.openai_agents import OpenAIAgentsToolCompatibilityProposal
from packages.adapters.capabilities.openai_computer_use import OpenAIComputerUseHarnessConfig
from packages.adapters.capabilities.openai_tools import OpenAIFunctionToolProposal
from packages.capability_runtime import (
    ApprovalDecision,
    CapabilityExecutionMode,
    CapabilityPermissionDecision,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


def _approved_permission(proposal):
    return CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-1",
        capability_ref=proposal.to_capability_proposal().capability_ref,
        decision="approved",
        reason_code="policy_allowed",
        human_approval=HumanApprovalRequirement(
            required=proposal.requires_approval,
            reason_code="approval_required" if proposal.requires_approval else "not_required",
            prompt_user_visible=proposal.requires_approval,
            risk_level=proposal.risk_level,
            side_effect_level=proposal.side_effect_level,
        ),
    )


def _approval_decision(proposal) -> ApprovalDecision:
    return ApprovalDecision(
        schema_version="1",
        decision_id="approval-1",
        approval_request_id="approval-request-1",
        capability_ref=proposal.to_capability_proposal().capability_ref,
        decision="approved",
        decided_by="user",
    )


def test_builtin_tools_execute_only_safe_readonly_capabilities() -> None:
    catalog = BuiltinToolCatalog.default()
    calculator = catalog.calculator().execute(CalculatorRequest(expression="2 + 3 * 4"))
    clock = catalog.time_date(clock=lambda: dt.datetime(2026, 5, 18, 12, 30, tzinfo=dt.timezone.utc))
    time_result = clock.execute(TimeDateRequest(timezone="UTC"))
    diagnostics = catalog.capability_diagnostics(capability_count=7, eligible_count=2).execute()
    repo = catalog.repo_status(snapshot=RepoStatusSnapshot(branch="main", clean=True, short_status="")).execute()

    assert calculator.safe_result["result"] == "14"
    assert time_result.safe_result["iso_date"] == "2026-05-18"
    assert diagnostics.safe_result["capability_count"] == 7
    assert repo.safe_result["clean"] is True
    assert all(manifest.enabled_by_default is False for manifest in catalog.manifests())

    with pytest.raises(ValidationError):
        CalculatorRequest(expression="__import__('os').system('whoami')")


def test_playwright_browser_adapter_models_risk_and_requires_approval_for_actions() -> None:
    config = PlaywrightBrowserAdapterConfig(
        schema_version="1",
        adapter_id="playwright-local",
        headless=True,
        isolated_session_required=True,
    )
    session = BrowserSessionRef(session_id="browser-session-1")
    read = BrowserActionProposal(
        schema_version="1",
        proposal_id="read-page-1",
        trace_id="trace-1",
        turn_id="turn-1",
        session_ref=session,
        action_kind=BrowserActionKind.READ_PAGE,
        target="active_page",
    )
    click = BrowserActionProposal(
        schema_version="1",
        proposal_id="click-1",
        trace_id="trace-1",
        turn_id="turn-1",
        session_ref=session,
        action_kind=BrowserActionKind.CLICK,
        target="#submit",
    )

    assert config.backend == "playwright"
    assert read.requires_approval is False
    assert click.requires_approval is True
    assert click.to_capability_proposal().risk_level is ToolRiskLevel.HIGH

    with pytest.raises(ValidationError, match="requires approved human approval"):
        BrowserExecutionRequest.from_proposal(
            request_id="click-request-1",
            proposal=click,
            permission_decision=_approved_permission(click),
        )

    request = BrowserExecutionRequest.from_proposal(
        request_id="click-request-1",
        proposal=click,
        permission_decision=_approved_permission(click),
        approval_decision=_approval_decision(click),
    )
    result = BrowserResultEnvelope.from_execution(
        request,
        result_id="browser-result-1",
        status="succeeded",
        safe_result={"action_kind": "click", "element_count": 1},
    )

    assert request.execution_request.execution_mode is CapabilityExecutionMode.APPROVED_EXECUTE
    assert result.raw_dom_persisted is False
    assert result.raw_screenshot_persisted is False


def test_browser_use_seam_is_disabled_until_dependency_is_approved_for_execution() -> None:
    config = BrowserUseAdapterConfig(
        schema_version="1",
        adapter_id="browser-use-foundation",
        backend_enabled=False,
        blocked_reason="agentic_backend_requires_future_policy_review",
    )
    proposal = BrowserUseTaskProposal(
        schema_version="1",
        proposal_id="browser-use-task-1",
        trace_id="trace-1",
        turn_id="turn-1",
        task_summary="Find safe public documentation for a library.",
    )
    request = BrowserUseExecutionRequest.from_proposal(
        request_id="browser-use-request-1",
        proposal=proposal,
        permission_decision=_approved_permission(proposal),
    )

    assert config.safe_projection()["backend_enabled"] is False
    assert proposal.requires_approval is True
    assert request.safe_result_envelope(result_id="browser-use-result-1").status == "denied"


def test_browser_use_backend_can_be_imported_but_not_executed_without_policy() -> None:
    probe = BrowserUseBackendProbe.from_installed_backend()
    config = BrowserUseAdapterConfig(
        schema_version="1",
        adapter_id="browser-use-foundation",
        backend_enabled=False,
        blocked_reason="browser_use_backend_installed_but_execution_disabled_by_policy",
    )

    assert probe.backend_name == "browser-use"
    assert probe.package_importable is True
    assert probe.sdk_package_importable is True
    assert probe.execution_supported_without_approval is False
    assert config.safe_projection()["backend_enabled"] is False
    assert probe.safe_projection()["playwright_remains_low_level_backend"] is True


def test_openai_computer_use_seam_requires_approval_and_treats_screen_as_untrusted() -> None:
    config = OpenAIComputerUseHarnessConfig(
        schema_version="1",
        adapter_id="openai-computer-use",
        isolated_environment_required=True,
        screen_content_untrusted=True,
    )
    task = ComputerUseTaskProposal(
        schema_version="1",
        proposal_id="computer-task-1",
        trace_id="trace-1",
        turn_id="turn-1",
        task_summary="Use an isolated browser to inspect a public page.",
        harness_config=ComputerUseHarnessConfig.from_openai(config),
    )
    action = ComputerUseActionProposal.from_task(
        task,
        action_id="computer-action-1",
        action_summary="Click the next button in the isolated browser.",
    )

    assert action.requires_approval is True
    assert action.harness_config.screen_content_untrusted is True
    assert action.to_capability_proposal().side_effect_level is ToolSideEffectLevel.DESKTOP_ACTION

    result = ComputerUseResultEnvelope.from_proposal(
        action,
        result_id="computer-result-1",
        status="requires_human_approval",
        safe_result={"pending_approval": True},
    )
    assert result.raw_screen_persisted is False


def test_provider_tool_call_adapters_create_proposals_not_execution_permission() -> None:
    openai = OpenAIFunctionToolProposal(
        schema_version="1",
        proposal_id="openai-tool-1",
        trace_id="trace-1",
        turn_id="turn-1",
        function_name="lookup_order",
        json_schema={"type": "object"},
    )
    lmstudio = LMStudioLocalToolProposal(
        schema_version="1",
        proposal_id="lmstudio-tool-1",
        trace_id="trace-1",
        turn_id="turn-1",
        tool_name="local_lookup",
        marvex_policy_authoritative=True,
    )
    litellm = LiteLLMToolCallProposal(
        schema_version="1",
        proposal_id="litellm-tool-1",
        trace_id="trace-1",
        turn_id="turn-1",
        tool_name="gateway_lookup",
        toolset_ref=LiteLLMToolsetRef(toolset_id="gateway", external_permission_source="marvex"),
    )
    agents = OpenAIAgentsToolCompatibilityProposal(
        schema_version="1",
        proposal_id="agents-tool-1",
        trace_id="trace-1",
        turn_id="turn-1",
        tool_name="agent_tool",
        tool_schema={"type": "object"},
    )

    proposals = [
        openai.to_capability_proposal(),
        lmstudio.to_capability_proposal(),
        litellm.to_capability_proposal(),
        agents.to_capability_proposal(),
    ]

    assert all(proposal.execution_mode is CapabilityExecutionMode.PROPOSAL_ONLY for proposal in proposals)
    assert all(proposal.raw_arguments_persisted is False for proposal in proposals)


def test_openai_agents_sdk_import_maps_to_marvex_policy_proposal() -> None:
    agents = OpenAIAgentsToolCompatibilityProposal.from_installed_sdk_tool(
        schema_version="1",
        proposal_id="agents-tool-2",
        trace_id="trace-1",
        turn_id="turn-1",
        tool_name="lookup_docs",
        tool_schema={"type": "object"},
    )

    proposal = agents.to_capability_proposal()

    assert agents.agents_sdk_tool_present is True
    assert agents.agents_sdk_owns_execution is False
    assert agents.marvex_policy_authoritative is True
    assert proposal.execution_mode is CapabilityExecutionMode.PROPOSAL_ONLY
