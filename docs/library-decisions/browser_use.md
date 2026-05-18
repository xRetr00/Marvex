# Library Decision: Browser-use Adapter Seam

library name: browser-use

official source: https://github.com/browser-use/browser-use and https://pypi.org/project/browser-use/

maintenance status: Active as of May 18, 2026. PyPI latest version observed locally with `python -m pip index versions browser-use` as `browser-use==0.12.6`.

why use it: Browser-use is a maintained agentic browser automation project and is relevant to future high-level browser task execution. It should be considered before Marvex custom-builds an agentic browser task runner.

why not custom code: A custom agentic browser-use layer would duplicate a large maintained surface. However, adopting Browser-use as an executable backend now would import agent loop, model/provider, browser task autonomy, and execution semantics before Marvex has a mature policy/UI approval flow.

fallback if abandoned: Keep `packages.adapters.capabilities.browser_use` as a disabled adapter seam with safe proposals and result envelopes. Future work can adopt the dependency behind that seam or keep using Playwright directly behind Marvex policy.

pyproject dependency: none

declared dependency: not declared

verified date: 2026-05-18

verified by: Codex

scope: Adapter seam only. `BrowserUseTaskProposal`, `BrowserUseAdapterConfig`, `BrowserUseExecutionRequest`, and safe result envelopes exist, but backend execution remains disabled.

architecture fit: Deferred. The project is relevant, but the current foundation must keep CapabilityRuntime authoritative and avoid importing external agent autonomy or hidden browser execution.

adopt / defer / reject decision: Defer backend adoption. Implement the adapter boundary now and mark backend execution blocked by future policy review.

risks: Browser-use can combine model planning with browser actions, which risks hidden tool loops, prompt injection through page content, credential entry, form submission, raw page persistence, and external execution outside Marvex approval policy. Current mitigation is a disabled backend seam with explicit approval-required proposals.

comparison to custom routing: Browser-use is not Marvex's planner or assistant loop. If adopted later, it must stay behind adapter and CapabilityRuntime execution envelopes.
