# Library Decision: Assistant Intelligence and Tool-Using Runtime Integration

library name: Semantic Router, Playwright Python, MCP Python SDK, OpenAI-compatible tool-call shapes, LM Studio tool-call shapes, LiteLLM tool-call shapes

official source: https://semantic-router.readthedocs.io/, https://playwright.dev/python/, https://github.com/modelcontextprotocol/python-sdk, https://platform.openai.com/docs/guides/tools, https://lmstudio.ai/docs, https://docs.litellm.ai/

maintenance status: Playwright, MCP Python SDK, OpenAI Python/API tool-call surfaces, LM Studio OpenAI-compatible local API behavior, and LiteLLM remain appropriate maintained surfaces for adapter-backed mechanics. Semantic Router remains maintained but still requires an encoder/embedding decision before Marvex should adopt it as a runtime dependency.

why use it: Browser automation and MCP protocol mechanics are not Marvex inventions and stay behind adapters. Provider tool calls should be translated from maintained provider shapes into Marvex-owned `CapabilityCallProposal` objects instead of becoming direct execution permission. Semantic routing is still represented behind an adapter seam so Marvex can adopt a maintained router later without moving policy into Core.

why not custom code: Custom browser automation, MCP protocol mechanics, provider tool-call parsing, or semantic routing would increase ownership drift and policy bypass risk. Marvex keeps protocol mechanics in adapters and keeps CapabilityRuntime authoritative for permissions, approvals, dispatch, execution requests, and result envelopes.

fallback if abandoned: Keep deterministic intent routing and provider tool-call mapper tests as safe proof backends. Disable live browser or MCP execution paths by configuration if SDKs become unavailable. Keep provider tool calls as proposals and continue with safe built-in tool execution proof.

pyproject dependency: no new dependency in this checkpoint; existing dependencies remain `playwright==1.59.0`, `mcp==1.27.1`, `openai==2.24.0`, and `litellm==1.83.13`.

declared dependency: none added

verified date: 2026-05-18

verified by: Codex

scope: Deeper runtime integration only. No generic provider routing, no model selection, no autonomous planner, no shell/filesystem write execution, no arbitrary MCP server launch, no arbitrary browser/computer action, no credential entry/extraction, no payment/checkout, no CAPTCHA bypass, and no raw payload persistence by default.

adopt / defer / reject decision:

- Playwright Python: adopted already behind `packages.adapters.capabilities.browser`; this checkpoint adds a safe workflow executor over approved `BrowserExecutionRequest` objects.
- MCP Python SDK: adopted already behind `packages.adapters.capabilities.mcp`; this checkpoint uses only allowlisted fake/local SDK-session proof paths.
- OpenAI-compatible provider tool calls: adapter mapping now, execution deferred to CapabilityRuntime approvals/dispatch.
- LM Studio tool calls: adapter mapping now through OpenAI-compatible local shapes, no LM Studio-owned execution.
- LiteLLM tool calls: adapter mapping now, no LiteLLM-owned execution.
- Semantic Router: backend remains deferred; adapter seam and deterministic proof backend remain because an encoder/vector dependency decision is still required.

risks: Provider tool-call schemas can contain raw arguments, MCP tool outputs can contain raw text, and browser extraction can contain page content. Current mitigation is safe schema/projection mapping, result metadata instead of raw payload persistence, allowlists, blocked dangerous MCP tool names, approval pause/resume state, and boundary gates.
