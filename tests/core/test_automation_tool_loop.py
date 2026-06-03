"""Model-callable browser/desktop automation tools in the agentic loop (TODO 08)."""

import json

from packages.adapters.capabilities.tools import ToolRegistry, default_registry
from packages.adapters.capabilities.tools.automation import (
    BrowserUseTool,
    ComputerUseTool,
    PlaywrightBrowserTool,
)
from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.core.orchestration.agentic_tools import ProviderStep, execute_tool_calls, run_tool_loop
from packages.telemetry import InMemoryTraceReader
from services.core.main import _CoreServiceProviderWorkerTurnExecutor
from services.core.main import _auto_approve_pending_tool


def _registry() -> ToolRegistry:
    return ToolRegistry((*default_registry().tools(), BrowserUseTool(), ComputerUseTool(), PlaywrightBrowserTool()))


def _call(name: str, args: dict) -> dict:
    return {"id": f"call-{name}", "function": {"name": name, "arguments": json.dumps(args)}}


def test_browser_use_tool_pauses_for_approval_carrying_capability_and_args():
    outcome = execute_tool_calls(
        [_call("builtin.browser_use", {"task": "open youtube"})],
        registry=_registry(),
        request_builder=lambda name, args: None,
    )
    autos = outcome.automation_calls
    assert len(autos) == 1
    a = autos[0].automation
    assert a["capability_id"] == "browser_use.task"
    assert a["resource_type"] == "browser"
    assert a["arguments"] == {"task": "open youtube"}
    assert autos[0].pending_tool["capability_id"] == "browser_use.task"
    assert autos[0].pending_tool["arguments"] == {"task": "open youtube"}
    # Not executed in the loop.
    assert outcome.executed_tool_ids == []


def test_loop_returns_needs_approval_with_automation_payload():
    def send(input_text, tool_messages, prev):
        return ProviderStep(output_text="", tool_calls=[_call("builtin.computer_use", {"action_summary": "open notepad", "action_kind": "open_app"})], response_id="r1", error=False)

    result = run_tool_loop(send=send, registry=_registry(), request_builder=lambda n, a: None, max_steps=3, initial_input="open notepad")
    assert result.status == "needs_approval"
    assert result.automation is not None
    assert result.automation["capability_id"] == "computer_use.action"
    assert result.automation["resource_type"] == "desktop"
    assert result.response_id == "r1"


def test_auto_marvex_policy_auto_approves_browser_and_playwright_pending_tools():
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)
    ask_policy = AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY)

    assert _auto_approve_pending_tool(policy, {"capability_id": "browser_use.task"}) is True
    assert _auto_approve_pending_tool(policy, {"capability_id": "playwright_mcp.task"}) is True
    assert _auto_approve_pending_tool(policy, {"capability_id": "computer_use.action"}) is True
    assert _auto_approve_pending_tool(policy, {"capability_id": "file.write"}) is True
    assert _auto_approve_pending_tool(policy, {"capability_id": "file.delete"}) is True
    assert _auto_approve_pending_tool(policy, {"capability_id": "future.unknown_tool"}) is True
    assert _auto_approve_pending_tool(ask_policy, {"capability_id": "browser_use.task"}) is False


def test_automation_tools_are_in_the_model_schema():
    schemas = _registry().tool_schemas()
    names = {str((sc.get("function") or {}).get("name") or sc.get("name") or "").rsplit(".", 1)[-1] for sc in schemas}
    assert {"browser_use", "computer_use", "playwright_browser"} <= names


def test_core_can_limit_browser_computer_route_to_automation_tools():
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
    )
    try:
        registry = executor._agentic_tool_registry(
            allowed_tool_ids={
                "builtin.clarify",
                "builtin.browser_use",
                "builtin.playwright_browser",
                "builtin.computer_use",
            }
        )
        names = {str((sc.get("function") or {}).get("name") or sc.get("name") or "") for sc in registry.tool_schemas()}

        assert names == {
            "builtin.clarify",
            "builtin.browser_use",
            "builtin.playwright_browser",
            "builtin.computer_use",
        }
    finally:
        executor.shutdown()
