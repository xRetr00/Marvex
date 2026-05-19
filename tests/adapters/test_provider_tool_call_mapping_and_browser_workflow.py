from __future__ import annotations

from packages.adapters.capabilities.browser import (
    BrowserActionKind,
    BrowserActionProposal,
    BrowserExecutionRequest,
    BrowserSessionRef,
    PlaywrightBrowserWorkflow,
    PlaywrightSdkBoundary,
)
from packages.adapters.providers.tool_calls import (
    ProviderToolCallMapper,
    ProviderToolCallSource,
)
from packages.adapters.capabilities.browser_use import BrowserUseBackendProbe, BrowserUseControlledBackend, BrowserUseTaskProposal
from packages.capability_runtime import (
    ApprovalDecision,
    CapabilityPermissionDecision,
    HumanApprovalRequirement,
)


class FakePage:
    def __init__(self) -> None:
        self.visited: list[str] = []

    def title(self) -> str:
        return "Example Page"

    def inner_text(self, selector: str) -> str:
        assert selector == "body"
        return "Public page text that must not be fully persisted in telemetry or results."

    def goto(self, target: str, wait_until: str = "domcontentloaded") -> None:
        self.visited.append(f"{target}:{wait_until}")


def _permission(proposal: BrowserActionProposal) -> CapabilityPermissionDecision:
    cap = proposal.to_capability_proposal()
    return CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-browser-1",
        capability_ref=cap.capability_ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(
            required=proposal.requires_approval,
            reason_code="approval_required" if proposal.requires_approval else "not_required",
            prompt_user_visible=proposal.requires_approval,
            risk_level=proposal.risk_level,
            side_effect_level=proposal.side_effect_level,
        ),
    )


def _approval(proposal: BrowserActionProposal) -> ApprovalDecision:
    return ApprovalDecision(
        schema_version="1",
        decision_id="approval-browser-1",
        approval_request_id="approval-browser-1",
        capability_ref=proposal.to_capability_proposal().capability_ref,
        decision="approved",
        decided_by="user",
    )


def _proposal(kind: BrowserActionKind) -> BrowserActionProposal:
    return BrowserActionProposal(
        schema_version="1",
        proposal_id=f"browser-{kind.value}-1",
        trace_id="trace-browser-1",
        turn_id="turn-browser-1",
        session_ref=BrowserSessionRef(session_id="isolated-browser-1"),
        action_kind=kind,
        target="https://example.test/page" if kind == BrowserActionKind.NAVIGATE else "body",
    )


def test_playwright_browser_workflow_executes_readonly_extract_as_safe_projection() -> None:
    proposal = _proposal(BrowserActionKind.EXTRACT_TEXT)
    request = BrowserExecutionRequest.from_proposal(
        request_id="browser-request-1",
        proposal=proposal,
        permission_decision=_permission(proposal),
    )

    result = PlaywrightBrowserWorkflow(boundary=PlaywrightSdkBoundary(page=FakePage())).execute(request)

    assert result.result.status == "succeeded"
    assert result.result.safe_result == {
        "action_kind": "extract_text",
        "text_character_count": 74,
        "text_preview_present": True,
        "raw_page_text_persisted": False,
    }
    assert "Public page text" not in result.model_dump_json()
    assert result.raw_dom_persisted is False
    assert result.raw_page_text_persisted is False


def test_playwright_browser_workflow_requires_approved_capability_request_for_navigation() -> None:
    proposal = _proposal(BrowserActionKind.NAVIGATE)
    request = BrowserExecutionRequest.from_proposal(
        request_id="browser-request-2",
        proposal=proposal,
        permission_decision=_permission(proposal),
        approval_decision=_approval(proposal),
    )
    page = FakePage()

    result = PlaywrightBrowserWorkflow(boundary=PlaywrightSdkBoundary(page=page)).execute(request)

    assert page.visited == ["https://example.test/page:domcontentloaded"]
    assert result.result.status == "succeeded"
    assert result.result.safe_result["action_kind"] == "navigate"
    assert result.result.safe_result["target_persisted"] is False


def test_provider_tool_call_mapper_turns_supported_provider_shapes_into_policy_proposals() -> None:
    mapper = ProviderToolCallMapper(schema_version="1", trace_id="trace-provider-tools-1", turn_id="turn-provider-tools-1")

    openai = mapper.from_openai_compatible(
        {"id": "call_1", "function": {"name": "calculator", "arguments": "{\"expression\": \"2+2\"}"}},
        source=ProviderToolCallSource.OPENAI_COMPATIBLE,
    )
    lmstudio = mapper.from_openai_compatible(
        {"id": "call_2", "function": {"name": "local_lookup", "arguments": "{}"}},
        source=ProviderToolCallSource.LMSTUDIO,
    )
    litellm = mapper.from_litellm({"id": "call_3", "name": "gateway_lookup", "arguments": {"q": "weather"}})

    proposals = (openai.to_capability_proposal(), lmstudio.to_capability_proposal(), litellm.to_capability_proposal())
    assert [proposal.capability_ref.identifier for proposal in proposals] == [
        "openai.calculator",
        "lmstudio.local_lookup",
        "litellm.gateway_lookup",
    ]
    assert all(proposal.execution_mode.value == "proposal_only" for proposal in proposals)
    assert all(proposal.raw_arguments_persisted is False for proposal in proposals)
    assert all("expression" not in proposal.model_dump_json() for proposal in proposals)



def test_provider_tool_call_mapper_marks_unsafe_tool_name_without_silent_normalization() -> None:
    mapper = ProviderToolCallMapper(schema_version="1", trace_id="trace-provider-tools-1", turn_id="turn-provider-tools-1")

    proposal = mapper.from_openai_compatible(
        {"id": "call_unsafe", "function": {"name": "calculator;send_email", "arguments": "{}"}},
        source=ProviderToolCallSource.OPENAI_COMPATIBLE,
    )

    assert proposal.tool_name_status == "unsafe"
    assert proposal.original_tool_name_persisted is False
    assert proposal.to_capability_proposal().proposed_action == "blocked_provider_tool"
    assert "send_email" not in proposal.model_dump_json().lower()


def test_browser_use_controlled_backend_reports_policy_gated_status_without_sdk_execution() -> None:
    probe = BrowserUseBackendProbe.from_installed_backend()
    proposal = BrowserUseTaskProposal(
        schema_version="1",
        proposal_id="browser-use-proof-1",
        trace_id="trace-browser-use-1",
        turn_id="turn-browser-use-1",
        task_summary="Navigate to a public page and read text",
    )

    backend = BrowserUseControlledBackend.from_probe(probe)
    projection = backend.safe_projection()
    result = backend.preview_allowed_task(proposal)

    assert projection["execution_mode"] == "controlled_adapter_proof"
    assert projection["requires_capability_runtime_approval"] is True
    assert projection["direct_sdk_execution_enabled"] is False
    assert result.status == "denied"
    assert result.safe_result["blocked_reason"] == "browser_use_direct_execution_blocked_until_policy_worker_boundary"
    assert result.safe_result["allowed_actions"] == ("navigate", "read_page", "extract_text", "screenshot_metadata")
    assert result.raw_input_persisted is False
    assert result.raw_output_persisted is False
