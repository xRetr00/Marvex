# Library Decision: Assistant Intelligence and Tool-Using Runtime Integration

library name: Semantic Router, Playwright Python, MCP Python SDK, OpenAI-compatible tool-call shapes, LM Studio tool-call shapes, LiteLLM tool-call shapes

official source: https://semantic-router.readthedocs.io/, https://playwright.dev/python/, https://github.com/modelcontextprotocol/python-sdk, https://platform.openai.com/docs/guides/tools, https://lmstudio.ai/docs, https://docs.litellm.ai/

maintenance status: Playwright, MCP Python SDK, OpenAI Python/API tool-call surfaces, LM Studio OpenAI-compatible local API behavior, and LiteLLM remain appropriate maintained surfaces for adapter-backed mechanics. Semantic Router is adopted behind the intent adapter; Playwright, MCP Python SDK, OpenAI Python/API tool-call surfaces, LM Studio OpenAI-compatible local API behavior, and LiteLLM remain appropriate maintained surfaces for adapter-backed mechanics.

why use it: Browser automation and MCP protocol mechanics are not Marvex inventions and stay behind adapters. Provider tool calls should be translated from maintained provider shapes into Marvex-owned `CapabilityCallProposal` objects instead of becoming direct execution permission. Semantic routing is still represented behind an adapter seam so Marvex can adopt a maintained router later without moving policy into Core.

why not custom code: Custom browser automation, MCP protocol mechanics, provider tool-call parsing, or semantic routing would increase ownership drift and policy bypass risk. Marvex keeps protocol mechanics in adapters and keeps CapabilityRuntime authoritative for permissions, approvals, dispatch, execution requests, and result envelopes.

fallback if abandoned: Keep deterministic intent routing and provider tool-call mapper tests as safe proof backends. Disable live browser or MCP execution paths by configuration if SDKs become unavailable. Keep provider tool calls as proposals and continue with safe built-in tool execution proof.

pyproject dependency: existing adapter dependencies include `semantic-router==0.1.14`, `playwright==1.60.0`, `mcp==1.27.1`, `openai==2.37.0`, `openai-agents==0.17.2`, `litellm==1.85.0`, and `browser-use==0.11.13`.

declared dependency: see individual runtime library decision records

verified date: 2026-05-19

verified by: Codex

scope: Deeper runtime integration only. This checkpoint includes provider tool-call proposal mapping into Marvex-approved safe execution, safe provider continuation input construction, final fake-provider continuation response representation, malformed provider argument rejection, safe Playwright read/navigation workflow execution after approval, allowlisted MCP proof execution, SQLite memory backend safe-ref participation, semantic-router-backed IntentRuntime classification injection, Memory Tree evidence refs in context/prompt/telemetry/control summaries, and trace-searchable safe runtime summaries. No generic provider routing, no model selection, no autonomous planner, no shell/filesystem write execution, no arbitrary MCP server launch, no arbitrary browser/computer action, no credential entry/extraction, no payment/checkout, no CAPTCHA bypass, and no raw payload persistence by default.

adopt / defer / reject decision:

audit classification:

- Real runtime behavior: safe built-in calculator execution, provider tool-call proposal mapping into CapabilityRuntime execution for approved safe tools, safe provider continuation input with result-key summaries, final response representation after tool result, malformed provider argument denial without fallback execution, Playwright read/extract/navigation workflow metadata after policy approval, approval pause/resume/deny/cancel state, allowlisted MCP proof execution, prompt/context budget projections, safe trace summaries, and Memory Tree evidence-ref context inclusion.
- Proof-only behavior: fake provider continuation model call, LM Studio/OpenAI/LiteLLM tool-call shape compatibility, local/fake MCP sessions, and browser-use import-backed support.
- Disabled seams: arbitrary browser/computer execution, browser-use execution, arbitrary MCP server launch/install, broad account/OAuth sync, shell/filesystem tools, and generic provider routing/model selection.
- Missing but intentionally blocked: service daemon behavior, retry/fallback/model selection, live OAuth ingestion, voice, Orb/Face shell, desktop overlay, proactive behavior, credential entry/extraction, payment/checkout, CAPTCHA bypass, and raw payload persistence.

- Playwright Python: adopted already behind `packages.adapters.capabilities.browser`; this checkpoint adds a safe workflow executor over approved `BrowserExecutionRequest` objects.
- MCP Python SDK: adopted already behind `packages.adapters.capabilities.mcp`; this checkpoint uses only allowlisted fake/local SDK-session proof paths.
- OpenAI-compatible provider tool calls: adapter mapping now, execution deferred to CapabilityRuntime approvals/dispatch.
- LM Studio tool calls: adapter mapping now through OpenAI-compatible local shapes, no LM Studio-owned execution.
- LiteLLM tool calls: adapter mapping now, no LiteLLM-owned execution.
- Semantic Router: adopted behind the intent adapter for no-cloud route definition and scoring proof; IntentRuntime remains policy owner.

risks: Provider tool-call schemas can contain raw arguments, MCP tool outputs can contain raw text, browser extraction can contain page content, and memory records can contain user content. Current mitigation is safe schema/projection mapping, result metadata instead of raw payload persistence, memory safe refs/previews only, allowlists, blocked dangerous MCP tool names, approval pause/resume state, trace-search safe summaries, and boundary gates.
