"""Tests for the per-file built-in tool registry (docs/TODO/07)."""

from packages.adapters.capabilities.tools import (
    CalculatorTool,
    ToolRegistry,
    default_registry,
)
from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


def _request(identifier: str, arguments: dict[str, object]) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=identifier)
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=ref,
        proposed_action="tool",
        risk_level=ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
        arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-1",
        capability_ref=ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    return CapabilityExecutionRequest(
        schema_version="1",
        request_id="request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        proposal=proposal,
        permission_decision=permission,
        arguments=arguments,
    )


def test_default_registry_dispatches_calculator():
    registry = default_registry()
    result = registry.execute(_request("builtin.calculator", {"expression": "2 + 2 * 3"}))
    assert result.status == "succeeded"
    assert result.safe_result["result"] == "8"


def test_default_registry_dispatches_time_date():
    registry = default_registry()
    # Default is local time (machine-dependent), so request UTC for a
    # deterministic, machine-independent assertion.
    result = registry.execute(_request("builtin.time_date", {"timezone": "UTC"}))
    assert result.status == "succeeded"
    assert "iso_datetime" in result.safe_result
    assert "display" in result.safe_result
    assert result.safe_result["timezone"] == "UTC"


def test_default_registry_time_date_defaults_to_local():
    registry = default_registry()
    result = registry.execute(_request("builtin.time_date", {}))
    assert result.status == "succeeded"
    # iso_datetime carries an explicit offset (local-aware), never a naive stamp.
    iso = str(result.safe_result["iso_datetime"])
    assert ("+" in iso[10:]) or ("-" in iso[10:]) or iso.endswith("+00:00")


def test_diagnostics_reports_live_tool_count():
    registry = default_registry()
    result = registry.execute(_request("builtin.capability_diagnostics", {}))
    assert result.status == "succeeded"
    assert result.safe_result["capability_count"] == len(registry.tools())


def test_unknown_identifier_is_denied_not_crash():
    registry = default_registry()
    result = registry.execute(_request("builtin.does_not_exist", {}))
    assert result.status == "denied"
    assert result.safe_result["reason_code"] == "tool.unsupported_capability"


def test_tool_schemas_are_model_callable_shapes():
    registry = default_registry()
    schemas = registry.tool_schemas()
    ids = {s["function"]["name"] for s in schemas}
    assert "builtin.calculator" in ids
    for schema in schemas:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert isinstance(fn["name"], str) and fn["name"]
        assert isinstance(fn["description"], str) and fn["description"]
        assert fn["parameters"]["type"] == "object"


def test_calculator_schema_exposes_expression_param():
    schema = CalculatorTool().json_schema()
    assert "expression" in schema["properties"]


def test_manifests_cover_every_registered_tool():
    registry = default_registry()
    manifests = registry.manifests()
    assert len(manifests) == len(registry.tools())
    identifiers = {m.capability_ref.identifier for m in manifests}
    assert "builtin.calculator" in identifiers


def test_duplicate_identifier_rejected():
    import pytest

    with pytest.raises(ValueError):
        ToolRegistry((CalculatorTool(), CalculatorTool()))
