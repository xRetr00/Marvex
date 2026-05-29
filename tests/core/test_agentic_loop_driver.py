"""Tests for the agentic tool-loop driver (docs/TODO/02, P2.3)."""

from pathlib import Path

from packages.adapters.capabilities.tools import ToolRegistry, default_registry, file_tools_registry
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
from packages.core.orchestration.agentic_tools import ProviderStep, run_tool_loop


def _combined_registry() -> ToolRegistry:
    return ToolRegistry((*default_registry().tools(), *file_tools_registry().tools()))


def _builder(root: str | None = None):
    def build(tool_id: str, arguments: dict) -> CapabilityExecutionRequest:
        ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=tool_id)
        args = dict(arguments)
        if root is not None and tool_id.startswith("file."):
            args.setdefault("root", root)
        proposal = CapabilityCallProposal(
            schema_version="1", proposal_id=f"p.{tool_id}", trace_id="t", turn_id="u",
            capability_ref=ref, proposed_action=tool_id, risk_level=ToolRiskLevel.SAFE,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, arguments_schema={"type": "object"},
        )
        permission = CapabilityPermissionDecision(
            schema_version="1", decision_id="d", capability_ref=ref, decision="approved",
            reason_code="ok", human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
        )
        return CapabilityExecutionRequest(
            schema_version="1", request_id="r", trace_id="t", turn_id="u",
            proposal=proposal, permission_decision=permission, arguments=args,
        )

    return build


def _fc(name: str, arguments: str, call_id: str = "c1") -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def test_immediate_text_answer_finalizes():
    sends = []

    def send(input_text, tool_messages, prev):
        sends.append((input_text, tool_messages, prev))
        return ProviderStep(output_text="hello there", tool_calls=[], response_id="r1", error=False)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="hi")
    assert result.status == "final"
    assert result.text == "hello there"
    assert result.steps == 1
    assert len(sends) == 1


def test_single_tool_call_then_text():
    # Step 1: model calls calculator. Step 2: model answers with the result.
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("builtin.calculator", '{"expression": "6*7"}')], response_id="r1", error=False),
        ProviderStep(output_text="The answer is 42.", tool_calls=[], response_id="r2", error=False),
    ]
    seen = []

    def send(input_text, tool_messages, prev):
        seen.append((input_text, tool_messages, prev))
        return steps.pop(0)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="what is 6*7")
    assert result.status == "final"
    assert result.text == "The answer is 42."
    assert result.executed_tool_ids == ["builtin.calculator"]
    assert result.steps == 2
    # Second send carried the tool result messages and the chained response id.
    assert seen[1][1] is not None  # tool_messages threaded
    assert any(m.get("role") == "tool" and "42" in str(m.get("content")) for m in seen[1][1])
    assert seen[1][2] == "r1"  # previous_response_id chained


def test_risky_tool_stops_for_approval(tmp_path: Path):
    def send(input_text, tool_messages, prev):
        return ProviderStep(
            output_text="", tool_calls=[_fc("file.write", '{"path": "x.txt", "content": "data"}')],
            response_id="r1", error=False,
        )

    result = run_tool_loop(send=send, registry=_combined_registry(), request_builder=_builder(root=str(tmp_path)), max_steps=5, initial_input="write a file")
    assert result.status == "needs_approval"
    assert result.needs_approval_tool_ids == ["file.write"]
    assert not (tmp_path / "x.txt").exists()  # never executed


def test_provider_error_returns_error_status():
    def send(input_text, tool_messages, prev):
        return ProviderStep(output_text="", tool_calls=[], response_id=None, error=True)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="hi")
    assert result.status == "error"


def test_max_steps_exhausted_when_model_keeps_calling_tools():
    def send(input_text, tool_messages, prev):
        # Always asks for a tool again -> never finalizes.
        return ProviderStep(output_text="", tool_calls=[_fc("builtin.time_date", "{}")], response_id="r", error=False)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=3, initial_input="time?")
    assert result.status == "max_steps"
    assert result.steps == 3
    assert result.executed_tool_ids == ["builtin.time_date", "builtin.time_date", "builtin.time_date"]


def test_real_file_read_through_loop(tmp_path: Path):
    (tmp_path / "note.txt").write_text("project alpha status: green", encoding="utf-8")
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("file.read", '{"path": "note.txt"}')], response_id="r1", error=False),
        ProviderStep(output_text="The note says project alpha is green.", tool_calls=[], response_id="r2", error=False),
    ]

    def send(input_text, tool_messages, prev):
        return steps.pop(0)

    result = run_tool_loop(send=send, registry=_combined_registry(), request_builder=_builder(root=str(tmp_path)), max_steps=5, initial_input="read note.txt and summarize")
    assert result.status == "final"
    assert result.executed_tool_ids == ["file.read"]
    assert "green" in result.text
