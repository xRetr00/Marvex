"""Model-callable browser/desktop automation tools in the agentic loop (TODO 08)."""

import json

from packages.adapters.capabilities.tools import ToolRegistry, default_registry
from packages.adapters.capabilities.tools.automation import (
    BrowserUseTool,
    ComputerUseTool,
    PlaywrightBrowserTool,
)
from packages.core.orchestration.agentic_tools import ProviderStep, execute_tool_calls, run_tool_loop


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


def test_automation_tools_are_in_the_model_schema():
    schemas = _registry().tool_schemas()
    names = {str((sc.get("function") or {}).get("name") or sc.get("name") or "").rsplit(".", 1)[-1] for sc in schemas}
    assert {"browser_use", "computer_use", "playwright_browser"} <= names
