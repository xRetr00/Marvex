from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.capability_runtime import (
    ApprovalDecision,
    ApprovalPrompt,
    CapabilityApprovalRequest,
    CapabilityCallProposal,
    CapabilityCompactionPolicy,
    CapabilityContextDeliveryPolicy,
    CapabilityEligibilityDecision,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityLoopGuard,
    CapabilityManifest,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityResultEnvelope,
    CapabilityStopReason,
    CapabilityToolContextDelivery,
    HumanApprovalRequirement,
    PendingApprovalState,
    ToolExecutionPolicy,
    ToolRiskLevel,
    ToolSideEffectLevel,
    ToolingTelemetrySummary,
    make_denial_result,
)


def _browser_ref() -> CapabilityRef:
    return CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click")


def test_tool_execution_policy_requires_human_approval_for_browser_actions() -> None:
    policy = ToolExecutionPolicy(
        schema_version="1",
        policy_id="browser-click-policy",
        capability_ref=_browser_ref(),
        risk_level=ToolRiskLevel.HIGH,
        side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
        execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
        human_approval=HumanApprovalRequirement(
            required=True,
            reason_code="browser_action_requires_confirmation",
            prompt_user_visible=True,
            risk_level=ToolRiskLevel.HIGH,
            side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
        ),
    )

    assert policy.requires_human_approval is True
    assert policy.safe_projection()["raw_policy_payload_persisted"] is False

    with pytest.raises(ValidationError, match="requires human approval"):
        ToolExecutionPolicy(
            schema_version="1",
            policy_id="unsafe-browser-policy",
            capability_ref=_browser_ref(),
            risk_level=ToolRiskLevel.HIGH,
            side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
            execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
            human_approval=HumanApprovalRequirement(
                required=False,
                reason_code="not_required",
                prompt_user_visible=False,
            ),
        )


def test_risky_execution_request_requires_matching_approval_decision() -> None:
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="browser-click-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=_browser_ref(),
        proposed_action="click",
        risk_level=ToolRiskLevel.HIGH,
        side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
        execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
        arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-1",
        capability_ref=_browser_ref(),
        decision="approved",
        reason_code="policy_allowed_after_approval",
        human_approval=HumanApprovalRequirement(
            required=True,
            reason_code="browser_action_requires_confirmation",
            prompt_user_visible=True,
            risk_level=ToolRiskLevel.HIGH,
            side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
        ),
    )

    with pytest.raises(ValidationError, match="requires approved human approval"):
        CapabilityExecutionRequest(
            schema_version="1",
            request_id="request-1",
            trace_id="trace-1",
            turn_id="turn-1",
            proposal=proposal,
            permission_decision=permission,
            arguments={"selector": "#submit"},
        )

    approval = ApprovalDecision(
        schema_version="1",
        decision_id="approval-1",
        approval_request_id="approval-request-1",
        capability_ref=_browser_ref(),
        decision="approved",
        decided_by="user",
    )
    request = CapabilityExecutionRequest(
        schema_version="1",
        request_id="request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        proposal=proposal,
        permission_decision=permission,
        approval_decision=approval,
        arguments={"selector": "#submit"},
        execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
    )

    assert request.execution_mode is CapabilityExecutionMode.APPROVED_EXECUTE
    assert request.safe_projection()["approval_decision"] == "approved"


def test_approval_request_pending_state_and_denial_result_are_safe() -> None:
    prompt = ApprovalPrompt(
        schema_version="1",
        prompt_id="approval-prompt-1",
        capability_ref=_browser_ref(),
        user_visible_summary="Allow browser click on the active page?",
        risk_level=ToolRiskLevel.HIGH,
        side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
    )
    approval_request = CapabilityApprovalRequest(
        schema_version="1",
        approval_request_id="approval-request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=_browser_ref(),
        prompt=prompt,
    )
    pending = PendingApprovalState.from_request(approval_request)
    denial = ApprovalDecision(
        schema_version="1",
        decision_id="approval-denial-1",
        approval_request_id=approval_request.approval_request_id,
        capability_ref=_browser_ref(),
        decision="denied",
        decided_by="user",
    )
    result = make_denial_result(
        approval_request=approval_request,
        approval_decision=denial,
        result_id="denied-result-1",
    )

    assert pending.safe_projection()["status"] == "pending"
    assert pending.safe_projection()["raw_prompt_persisted"] is False
    assert result.status == "denied"
    assert result.raw_output_persisted is False


def test_tool_context_delivery_includes_only_eligible_tool_schemas() -> None:
    eligible_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.calculator")
    browser_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.navigate")
    manifests = (
        CapabilityManifest(
            schema_version="1",
            capability_ref=eligible_ref,
            display_name="Calculator",
            description="Safe arithmetic calculator.",
            owner_package="packages.adapters.capabilities.builtins",
            adapter_boundary="builtins",
            input_schema={"type": "object"},
        ),
        CapabilityManifest(
            schema_version="1",
            capability_ref=browser_ref,
            display_name="Browser Navigate",
            description="Navigate an isolated browser page.",
            owner_package="packages.adapters.capabilities.browser",
            adapter_boundary="playwright_browser",
            input_schema={"type": "object"},
        ),
    )
    decisions = (
        CapabilityEligibilityDecision(
            schema_version="1",
            decision_id="eligible-1",
            capability_ref=eligible_ref,
            eligible=True,
            reason_code="intent_matched",
            intent_tags=("math",),
        ),
        CapabilityEligibilityDecision(
            schema_version="1",
            decision_id="excluded-1",
            capability_ref=browser_ref,
            eligible=False,
            reason_code="browser_not_requested",
            intent_tags=("browser",),
        ),
    )
    delivery = CapabilityToolContextDelivery(
        schema_version="1",
        trace_id="trace-1",
        turn_id="turn-1",
        manifests=manifests,
        eligibility_decisions=decisions,
        delivery_policy=CapabilityContextDeliveryPolicy(max_capabilities=4, include_excluded_reasons=True),
        compaction_policy=CapabilityCompactionPolicy(max_schema_bytes=2000, offload_large_schemas=True),
    )

    projected = delivery.schema_delivery()

    assert projected["all_tools_injected"] is False
    assert projected["included_tools"] == ["builtin.calculator"]
    assert projected["excluded_tools"] == ["browser.navigate"]


def test_loop_guard_tracks_human_approval_pause_and_repeated_failures() -> None:
    guard = CapabilityLoopGuard(
        schema_version="1",
        loop_id="tool-loop-1",
        max_steps=3,
        completed_steps=1,
        max_repeated_failures=2,
        repeated_failure_count=2,
    )
    approval_pause = CapabilityLoopGuard(
        schema_version="1",
        loop_id="tool-loop-2",
        max_steps=3,
        completed_steps=1,
        stop_reason=CapabilityStopReason.HUMAN_APPROVAL_REQUIRED,
        pause_reason="pending_human_approval",
    )

    assert guard.should_stop is True
    assert guard.stop_reason_effective == CapabilityStopReason.REPEATED_FAILURES
    assert approval_pause.should_stop is True


def test_tooling_telemetry_summary_counts_without_raw_payloads() -> None:
    summary = ToolingTelemetrySummary(
        schema_version="1",
        trace_id="trace-1",
        turn_id="turn-1",
        tool_proposal_count=4,
        approved_count=1,
        denied_count=1,
        executed_tool_count=1,
        browser_action_count=1,
        computer_action_count=0,
        high_risk_pending_approval_count=1,
    )

    assert summary.safe_projection()["browser_action_count"] == 1
    assert summary.raw_tool_payloads_persisted is False
    assert summary.raw_screenshots_persisted is False
