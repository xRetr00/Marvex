from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityKind,
    CapabilityManifest,
    CapabilityPermissionDecision,
    CapabilityRef,
    CapabilityExecutionRequest,
    HumanApprovalRequirement,
)


def test_capability_kind_covers_platform_surface() -> None:
    assert {kind.value for kind in CapabilityKind} == {
        "tool",
        "mcp_server",
        "mcp_tool",
        "skill",
        "plugin",
        "connector",
        "integration",
        "harness",
        "planner",
        "verifier",
    }


def test_manifest_safe_projection_omits_raw_prompt_or_result_material() -> None:
    manifest = CapabilityManifest(
        schema_version="1",
        capability_ref=CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier="mcp.weather.current"),
        display_name="Weather summary",
        description="Summarizes weather state without raw data persistence.",
        owner_package="packages.adapters.capabilities.mcp",
        adapter_boundary="mcp_adapter_disabled_backend",
        permissions=("read_weather",),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        metadata={"raw_prompt": "must not appear", "safe_tag": "forecast"},
    )

    assert manifest.safe_projection() == {
        "schema_version": "1",
        "capability_ref": {"kind": "mcp_tool", "identifier": "mcp.weather.current"},
        "display_name": "Weather summary",
        "owner_package": "packages.adapters.capabilities.mcp",
        "adapter_boundary": "mcp_adapter_disabled_backend",
        "permission_count": 1,
        "input_schema_present": True,
        "output_schema_present": True,
        "metadata_keys": ["[REDACTED]", "safe_tag"],
    }


def test_execution_request_requires_approved_permission() -> None:
    capability_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="fake.status")
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=capability_ref,
        proposed_action="fake_status",
        risk_level="low",
        arguments_schema={"type": "object"},
        raw_arguments_persisted=False,
    )
    denied = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="decision-1",
        capability_ref=capability_ref,
        decision="denied",
        reason_code="not_allowed",
        human_approval=HumanApprovalRequirement(
            required=True,
            reason_code="side_effect_possible",
            prompt_user_visible=False,
        ),
    )

    with pytest.raises(ValidationError):
        CapabilityExecutionRequest(
            schema_version="1",
            request_id="request-1",
            trace_id="trace-1",
            turn_id="turn-1",
            proposal=proposal,
            permission_decision=denied,
            arguments={"city": "Paris"},
            raw_arguments_persisted=False,
        )

    approved = denied.model_copy(update={"decision": "approved", "reason_code": "policy_allowlisted"})
    request = CapabilityExecutionRequest(
        schema_version="1",
        request_id="request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        proposal=proposal,
        permission_decision=approved,
        arguments={"city": "Paris"},
        raw_arguments_persisted=False,
    )

    assert request.safe_projection()["argument_keys"] == ["city"]
