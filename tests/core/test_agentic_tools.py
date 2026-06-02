"""Tests for the agentic tool-execution engine (docs/TODO/02, P2.2)."""

from pathlib import Path

from packages.adapters.capabilities.tools import ToolRegistry, default_registry, file_tools_registry, mcp_tools_registry, memory_tools_registry
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
from packages.core.orchestration.agentic_tools import (
    ProviderStep,
    execute_tool_calls,
    parse_tool_arguments,
    run_tool_loop,
)
from packages.memory_runtime import CurrentProcessMemoryStore


def _builder(root: str | None = None):
    def build(tool_id: str, arguments: dict) -> CapabilityExecutionRequest:
        kind = CapabilityKind.MCP_TOOL if tool_id.startswith("mcp.") else CapabilityKind.TOOL
        ref = CapabilityRef(kind=kind, identifier=tool_id)
        proposal = CapabilityCallProposal(
            schema_version="1",
            proposal_id=f"p.{tool_id}",
            trace_id="t-1",
            turn_id="u-1",
            capability_ref=ref,
            proposed_action=tool_id,
            risk_level=ToolRiskLevel.SAFE,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
            arguments_schema={"type": "object"},
        )
        permission = CapabilityPermissionDecision(
            schema_version="1",
            decision_id="d-1",
            capability_ref=ref,
            decision="approved",
            reason_code="policy_allowlisted",
            human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
        )
        args = dict(arguments)
        if root is not None and "root" not in args:
            args["root"] = root
        return CapabilityExecutionRequest(
            schema_version="1",
            request_id=f"r.{tool_id}",
            trace_id="t-1",
            turn_id="u-1",
            proposal=proposal,
            permission_decision=permission,
            arguments=args,
        )

    return build


def _call(name: str, arguments: str, call_id: str = "c1") -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def test_parse_tool_arguments_handles_json_string_dict_and_garbage():
    assert parse_tool_arguments('{"a": 1}') == {"a": 1}
    assert parse_tool_arguments({"a": 1}) == {"a": 1}
    assert parse_tool_arguments("not json") == {}
    assert parse_tool_arguments(None) == {}
    assert parse_tool_arguments("[1,2]") == {}  # non-dict json -> {}


def test_safe_tool_executes_and_returns_result_message():
    outcome = execute_tool_calls(
        [_call("builtin.calculator", '{"expression": "2 + 5"}')],
        registry=default_registry(),
        request_builder=_builder(),
    )
    assert outcome.executed_tool_ids == ["builtin.calculator"]
    assert outcome.tool_messages[0]["role"] == "tool"
    assert "7" in outcome.tool_messages[0]["content"]
    # Assistant message echoes the tool call (OpenAI protocol requirement).
    assert outcome.assistant_message["tool_calls"][0]["function"]["name"] == "builtin.calculator"


def test_unknown_tool_is_reported_not_executed():
    outcome = execute_tool_calls(
        [_call("agent.deep_search", "{}")],
        registry=default_registry(),
        request_builder=_builder(),
    )
    assert outcome.results[0].status == "unknown"
    assert "does not exist" in outcome.tool_messages[0]["content"]
    assert outcome.executed_tool_ids == []


def test_risky_tool_requires_approval_and_does_not_execute(tmp_path: Path):
    # file.write is MEDIUM risk -> must not auto-execute.
    outcome = execute_tool_calls(
        [_call("file.write", '{"path": "x.txt", "content": "data"}')],
        registry=file_tools_registry(),
        request_builder=_builder(root=str(tmp_path)),
    )
    assert outcome.results[0].status == "needs_approval"
    assert outcome.needs_approval
    assert outcome.pending_tool_calls[0].pending_tool["capability_id"] == "file.write"
    assert outcome.pending_tool_calls[0].pending_tool["arguments"] == {"path": "x.txt", "content": "data"}
    assert not (tmp_path / "x.txt").exists()  # never written


def test_write_local_memory_tools_require_approval_and_do_not_auto_execute():
    registry = memory_tools_registry(memory_store=CurrentProcessMemoryStore())
    outcome = execute_tool_calls(
        [_call("memory.remember", '{"content": "remember this: I prefer short answers"}')],
        registry=registry,
        request_builder=_builder(),
    )

    assert outcome.results[0].status == "needs_approval"
    assert outcome.executed_tool_ids == []
    assert outcome.pending_tool_calls[0].pending_tool["capability_id"] == "memory.remember"


def test_invalid_automation_tool_arguments_report_to_model_instead_of_approval():
    from packages.adapters.capabilities.tools.automation import BrowserUseTool

    outcome = execute_tool_calls(
        [_call("builtin.browser_use", '{"action_summary": "Open YouTube", "action_kind": "open_app"}')],
        registry=ToolRegistry((*default_registry().tools(), BrowserUseTool())),
        request_builder=_builder(),
    )

    assert outcome.results[0].status == "error"
    assert outcome.needs_approval == []
    assert "arguments are invalid" in outcome.tool_messages[0]["content"]


def test_loop_uses_later_valid_automation_call_when_first_call_has_wrong_schema():
    from packages.adapters.capabilities.tools.automation import BrowserUseTool

    registry = ToolRegistry((*default_registry().tools(), BrowserUseTool()))

    def send(_input_text, _tool_messages, _prev):
        return ProviderStep(
            output_text="",
            tool_calls=[
                _call(
                    "builtin.browser_use",
                    '{"action_summary": "Open YouTube in the browser", "action_kind": "open_app"}',
                    "bad",
                ),
                _call("builtin.browser_use", '{"task": "Navigate to youtube.com"}', "good"),
            ],
            response_id="r-browser",
            error=False,
        )

    result = run_tool_loop(
        send=send,
        registry=registry,
        request_builder=_builder(),
        max_steps=3,
        initial_input="open browser on youtube",
    )

    assert result.status == "needs_approval"
    assert result.pending_tool["call_id"] == "good"
    assert result.pending_tool["capability_id"] == "browser_use.task"
    assert result.pending_tool["arguments"] == {"task": "Navigate to youtube.com"}
    assert result.response_id == "r-browser"


def test_loop_carries_pending_file_write_payload_for_approval_resume():
    def send(_input_text, _tool_messages, _prev):
        return ProviderStep(
            output_text="",
            tool_calls=[_call("file.write", '{"path": "x.txt", "content": "data"}')],
            response_id="r-file-write",
            error=False,
        )

    result = run_tool_loop(
        send=send,
        registry=file_tools_registry(),
        request_builder=_builder(root="."),
        max_steps=3,
        initial_input="write a file",
    )

    assert result.status == "needs_approval"
    assert result.pending_tool["capability_id"] == "file.write"
    assert result.pending_tool["arguments"] == {"path": "x.txt", "content": "data"}
    assert result.response_id == "r-file-write"


def test_safe_file_read_executes(tmp_path: Path):
    (tmp_path / "note.txt").write_text("hello world", encoding="utf-8")
    outcome = execute_tool_calls(
        [_call("file.read", '{"path": "note.txt"}')],
        registry=file_tools_registry(),
        request_builder=_builder(root=str(tmp_path)),
    )
    assert outcome.executed_tool_ids == ["file.read"]
    assert "hello world" in outcome.tool_messages[0]["content"]


def test_mcp_tool_is_model_callable_and_executes_through_agentic_loop():
    registry = ToolRegistry(mcp_tools_registry().tools())
    schemas = registry.tool_schemas()

    outcome = execute_tool_calls(
        [_call("mcp.local.echo", '{"message": "hello from model"}')],
        registry=registry,
        request_builder=_builder(),
    )

    assert schemas[0]["function"]["name"] == "mcp.local.echo"
    assert outcome.executed_tool_ids == ["mcp.local.echo"]
    assert "hello from model" in outcome.tool_messages[0]["content"]


def test_multiple_calls_mixed_outcomes(tmp_path: Path):
    (tmp_path / "a.txt").write_text("aaa", encoding="utf-8")
    outcome = execute_tool_calls(
        [
            _call("file.read", '{"path": "a.txt"}', "c1"),
            _call("file.write", '{"path": "b.txt", "content": "x"}', "c2"),
            _call("nope.tool", "{}", "c3"),
        ],
        registry=file_tools_registry(),
        request_builder=_builder(root=str(tmp_path)),
    )
    statuses = {r.tool_id: r.status for r in outcome.results}
    assert statuses["file.read"] == "succeeded"
    assert statuses["file.write"] == "needs_approval"
    assert statuses["nope.tool"] == "unknown"
    # One tool message per call, each tagged with its call id.
    assert [m["tool_call_id"] for m in outcome.tool_messages] == ["c1", "c2", "c3"]


def test_failed_execution_becomes_error_message(tmp_path: Path):
    # Reading a missing file -> the read tool raises file.not_found internally;
    # the engine must turn that into an error tool-message, not crash.
    outcome = execute_tool_calls(
        [_call("file.read", '{"path": "does_not_exist.txt"}')],
        registry=file_tools_registry(),
        request_builder=_builder(root=str(tmp_path)),
    )
    assert outcome.results[0].status == "error"
    assert "error" in outcome.tool_messages[0]["content"].lower()
