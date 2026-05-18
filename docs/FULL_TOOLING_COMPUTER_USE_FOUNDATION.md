# Full Tooling and Computer Use Foundation

## Status

Full Tooling and Computer Use Foundation is implemented as a policy-gated adapter foundation. It adds real SDK-backed browser adapter mechanics through Playwright and safe proposal seams for Browser-use, OpenAI Computer Use, OpenAI Agents SDK tool compatibility, OpenAI function tools, LM Studio tool calls, LiteLLM gateway tools, MCP SDK tools, and built-in tools.

This is not a product tool loop, desktop agent, browser UI, credential manager, shell runtime, file editor, or autonomous computer-control system.

## Ownership

CapabilityRuntime remains authoritative for manifests, risk, side-effect classification, permissions, human approval requirements, approval prompts, approval decisions, execution modes, execution requests, result envelopes, context delivery, compaction, loop guards, and telemetry-safe summaries.

Adapters own SDK/package/protocol shape only:

- `packages.adapters.capabilities.browser` owns the Playwright browser adapter foundation.
- `packages.adapters.capabilities.browser_use` owns a disabled Browser-use seam.
- `packages.adapters.capabilities.computer_use` and `openai_computer_use` own computer-use proposal and harness shapes.
- `packages.adapters.capabilities.builtins` owns safe read-only built-in tools.
- `openai_tools`, `openai_agents`, `lmstudio`, `litellm_gateway`, and `mcp` represent provider or protocol tool calls as proposals, not execution permission.

## Safety Invariants

- All tool/browser/computer/provider tool calls are proposals or approved execution requests.
- Playwright is isolated behind the browser adapter only.
- Browser-use backend remains disabled until a future explicit policy review.
- OpenAI Computer Use is one adapter backend, not Marvex's only computer-use path.
- Browser and computer actions require human approval for high-impact action classes.
- No shell execution, file write/edit/delete, arbitrary network fetch, credential entry/extraction, payment/checkout, CAPTCHA/anti-bot bypass, stealth/proxy scraping, or arbitrary desktop OS control is implemented.
- Raw screenshots, DOM, page text, tool input/output, provider payloads, prompts, transcripts, tokens, and credentials are not persisted by default.
- Context delivery includes only eligible tool schemas; all tools are never injected into every prompt.

## Implemented Foundation

CapabilityRuntime now models `ToolRiskLevel`, `ToolSideEffectLevel`, `CapabilityExecutionMode`, `HumanApprovalRequirement`, `ApprovalPrompt`, `ApprovalDecision`, `CapabilityApprovalRequest`, `PendingApprovalState`, `ToolExecutionPolicy`, `CapabilityToolContextDelivery`, loop repeated-failure/human-approval pause handling, denial result envelopes, and `ToolingTelemetrySummary`.

Safe built-ins include calculator, UTC time/date, capability diagnostics, and injected read-only repo status snapshots. Session and memory diagnostics remain represented as safe projection capability context rather than direct runtime reads in this checkpoint.

## Blocked

- Browser-use execution backend is blocked because current adoption would import agentic browser task autonomy before Marvex has UI-backed approval and mature tool-loop governance.
- OpenAI Agents SDK package adoption is blocked because current `openai-agents==0.17.2` requires `openai>=2.26.0`, while Marvex currently pins `openai==2.24.0`; the compatibility seam exists without importing the package.
- Real OpenAI Computer Use execution is deferred to a future provider/runtime integration task.

## Validation

`tests/capability_runtime/test_full_tooling_policy_models.py` covers approval, risk, context delivery, loop guards, and telemetry-safe summaries.

`tests/tooling_adapters` covers built-ins, Playwright browser adapter models, Browser-use disabled seam, OpenAI Computer Use proposal seam, provider tool-call proposals, and ownership gates.

`scripts/check_full_tooling_boundaries.py` is included in `python scripts/run_all_checks.py`.
