"""Agentic automation tools — let the MODEL call browser/desktop automation as
tools (like any other tool-use/MCP call), gated through the human-approval flow.

These are HIGH-risk *control* tools. The agentic loop intercepts a call by id,
pauses for human approval, and on approve the Core executes the matching
capability (browser_use.task / computer_use.action / playwright_mcp.task) with the
model-supplied arguments + the user's configured provider. ``execute`` is a
harmless fallback for the Tool ABC; the loop never runs it directly.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result

BROWSER_USE_TOOL_ID = "browser_use"
COMPUTER_USE_TOOL_ID = "computer_use"
PLAYWRIGHT_MCP_TOOL_ID = "playwright_browser"

# tool_id -> (capability_id, resource_type, capability label) for the Core
# approval-execute step.
AUTOMATION_TOOL_CAPABILITIES: dict[str, tuple[str, str, str]] = {
    BROWSER_USE_TOOL_ID: ("browser_use.task", "browser", "browser_click_type"),
    COMPUTER_USE_TOOL_ID: ("computer_use.action", "desktop", "computer_actions"),
    PLAYWRIGHT_MCP_TOOL_ID: ("playwright_mcp.task", "browser", "browser_click_type"),
}


class BrowserUseParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(..., min_length=1, max_length=500, description="What to do in the web browser, in plain language.")


class BrowserUseTool(Tool):
    id: ClassVar[str] = BROWSER_USE_TOOL_ID
    name: ClassVar[str] = "Use the web browser"
    description: ClassVar[str] = (
        "Autonomously drive a managed web browser to accomplish a multi-step task such as navigating, "
        "reading, or filling forms. Give a clear task description."
    )
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.HIGH
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.BROWSER_ACTION
    params_model: ClassVar[type[BaseModel]] = BrowserUseParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        return succeeded_result(request, {"intercepted": True})


class ComputerUseParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_summary: str = Field(..., min_length=1, max_length=500, description="The desktop action to perform.")
    action_kind: str = Field(default="inspect", description="One of: inspect, screenshot, click, type, hotkey, focus, open_app.")


class ComputerUseTool(Tool):
    id: ClassVar[str] = COMPUTER_USE_TOOL_ID
    name: ClassVar[str] = "Control the desktop"
    description: ClassVar[str] = (
        "Perform a Windows desktop action such as inspecting the screen, clicking, typing, or opening an app."
    )
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.HIGH
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.DESKTOP_ACTION
    params_model: ClassVar[type[BaseModel]] = ComputerUseParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        return succeeded_result(request, {"intercepted": True})


class PlaywrightBrowserParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str = Field(default="", description="Playwright-MCP tool such as browser_navigate, browser_snapshot, browser_click, or browser_type.")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the selected Playwright-MCP tool.")
    url: str = Field(default="", description="URL to open, if navigating.")


class PlaywrightBrowserTool(Tool):
    id: ClassVar[str] = PLAYWRIGHT_MCP_TOOL_ID
    name: ClassVar[str] = "Browser (Playwright)"
    description: ClassVar[str] = (
        "Drive the user's already-open Chrome or Edge browser through the Playwright extension, reusing "
        "logged-in tabs and profile state. Use precise structured steps and chain calls as needed."
    )
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.HIGH
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.BROWSER_ACTION
    params_model: ClassVar[type[BaseModel]] = PlaywrightBrowserParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        return succeeded_result(request, {"intercepted": True})


__all__ = [
    "BrowserUseTool",
    "ComputerUseTool",
    "PlaywrightBrowserTool",
    "BROWSER_USE_TOOL_ID",
    "COMPUTER_USE_TOOL_ID",
    "PLAYWRIGHT_MCP_TOOL_ID",
    "AUTOMATION_TOOL_CAPABILITIES",
]
