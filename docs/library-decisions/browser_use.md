# Library Decision: Browser-use Adapter Backend

library name: browser-use

official source: https://github.com/browser-use/browser-use and https://pypi.org/project/browser-use/

maintenance status: Active as of May 18, 2026. `uv add browser-use` resolved the latest compatible main-environment version as `browser-use==0.11.13` with `openai==2.37.0`, `openai-agents==0.17.2`, `mcp==1.27.1`, `litellm==1.85.0`, `playwright==1.60.0`, `semantic-router==0.1.14`, and `Authlib==1.7.2`. A direct `uv add browser-use==0.12.6 --no-sync` failed because that release pins `openai==2.16.0`, conflicting with Marvex's OpenAI stack.

why use it: Browser-use is a maintained agentic browser automation project and is relevant to future high-level browser task execution. Marvex should evaluate and support it before custom-building an agentic browser task runner.

why not custom code: A custom agentic browser layer would duplicate a large maintained surface. Marvex still must not let Browser-use own the agent loop, model calls, browser task autonomy, policy, approval, memory, or prompt routing.

fallback if abandoned: Keep `packages.adapters.capabilities.browser_use` as an owner-mode adapter seam with safe probes, proposals, result envelopes, and precise failure reasons. Marvex can continue using Playwright directly behind CapabilityRuntime policy or route browser work through Playwright MCP later.

pyproject dependency: browser-use

declared dependency: browser-use==0.11.13

verified date: 2026-05-31

verified by: Codex

scope: Main-environment dependency import proof plus ToolWorker-owned personal owner-mode execution. `BrowserUseBackendProbe` verifies `browser_use` and `browser_use_sdk` importability. `BrowserUseTaskProposal`, `BrowserUseExecutionRequest`, and safe result envelopes require CapabilityRuntime approval resume before live execution. Raw DOM/screenshot/history/keystroke artifacts are allowed only through the approved `RawAutomationCapture` contract.

architecture fit: Approved for personal owner mode. The dependency is supported behind the adapter and ToolWorker boundary; Core remains orchestration-only and Playwright remains the deterministic low-level browser SDK path.

adopt / defer / reject decision: Adopt `browser-use==0.11.13` as a declared dependency for compatibility/import proof and owner-mode execution. Latest `browser-use==0.12.6` is blocked by an exact `openai==2.16.0` pin and must not downgrade Marvex's OpenAI stack.

risks: Browser-use can combine model planning with browser actions, which risks hidden tool loops, prompt injection through page content, credential entry, form submission, raw page persistence, and execution outside Marvex approval policy. Current mitigation is owner-mode approval resume through ToolWorker, explicit provider configuration for live runs, and raw artifact persistence through contract-owned artifact records instead of uncontrolled metadata.

comparison to custom routing: Browser-use is not Marvex's planner, assistant loop, browser policy owner, or provider router. Execution stays behind CapabilityRuntime-approved requests and result envelopes.

Browser-use backend runs in personal owner mode after CapabilityRuntime approval resume.
