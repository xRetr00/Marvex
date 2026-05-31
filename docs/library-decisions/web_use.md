# Library Decision: CursorTouch Web-Use

library name: CursorTouch/Web-Use

official source: https://github.com/CursorTouch/Web-Use

maintenance status: Active as of May 31, 2026. The repository describes Web-Use as a CDP-powered browser agent with system profile support, vision mode, semantic DOM tree extraction, file operations, OAuth/PKCE helpers, and WebMCP discovery.

why evaluate it: Web-Use overlaps Marvex's owner-mode browser-computer-use goals, especially real Chrome profile usage, CDP operation, semantic DOM state, vision-enabled interaction, WebMCP discovery, and authenticated workflows.

why use it: Use it as a reviewed future candidate for CDP/WebMCP browser automation if Marvex needs capabilities not covered by Browser-use or Playwright MCP.

why not custom code: Custom CDP browser-agent infrastructure would duplicate a maintained project surface for DOM extraction, browser profile handling, OAuth helpers, and WebMCP discovery.

why not adopt as primary now: It is a separate browser agent stack rather than a stable MCP server or simple SDK dependency already present in Marvex. Browser-use and Playwright MCP are already wired behind ToolWorker, and Web-Use needs a separate adapter spike before it can be admitted without duplicating policy, provider selection, artifact persistence, and approval flow.

fallback if abandoned: Continue with Browser-use for high-level browser agent loops and Playwright MCP/direct Playwright for deterministic browser actions. Web-Use remains optional behind a future `web_use.task` adapter if its API stabilizes for Marvex use.

pyproject dependency: none

declared dependency: none

verified date: 2026-05-31

verified by: Codex

scope: Reviewed for future Windows owner-mode browser automation. Not imported by Core. Not added as a dependency in this increment.

decision: Defer direct adoption, but keep it as a candidate backend for a future CDP/WebMCP browser adapter.

risks: Web-Use can interact with authenticated sessions, file uploads/downloads, OAuth tokens, DOM/page content, and vision captures. If adopted, it must use the same OwnerModeAutomationPolicy, RawAutomationCapture, destructive-action approval, and ToolWorker-owned result envelope rules as Browser-use, Playwright MCP, and Windows-MCP.
