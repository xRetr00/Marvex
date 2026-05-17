# Capability Platform Foundation

## Status

Capability Platform Foundation is implemented as a safe foundation layer. It is not a real tool runner, MCP host, browser/computer-use layer, account connector, or autonomous agent loop.

## Ownership

CapabilityRuntime owns manifests, capability refs, eligibility decisions, permission decisions, human approval requirements, context delivery policy, compaction policy, call proposals, execution requests, result/error envelopes, safe execution summaries, loop guards, planning readiness models, verification hooks, and safe projections.

Capability adapters own external protocol shape only. They cannot bypass CapabilityRuntime policy, cannot auto-call, cannot launch arbitrary MCP servers, cannot execute skill scripts, cannot store secrets by default, and cannot persist raw prompts, raw arguments, provider payloads, provider outputs, credentials, or transcripts by default.

AssistantRuntime may reference safe capability summary counts in lifecycle summaries. It does not import adapter packages, dispatch capabilities, execute tools, select tools, or own capability policy.

## Implemented Surfaces

- `packages/capability_runtime`: central Pydantic models, fake deterministic adapter, context delivery, compaction, loop guard, planning, verification, and safe summary projections.
- `packages/adapters/capabilities/mcp.py`: MCP server/tool refs, allowlist, transport enum for stdio/sse/streamable_http, SDK-backed allowlisted tool discovery, safe schema projection into CapabilityRuntime manifests, proposal creation, approved execution-request calls through the official SDK session, safe result envelopes, permission-gated request model, and disabled backend compatibility.
- `packages/adapters/capabilities/openai_tools.py`: OpenAI function tool, hosted tool, and remote MCP proposal seam. OpenAI tool calls remain proposals, not execution permission.
- `packages/adapters/capabilities/litellm_gateway.py`: LiteLLM toolset/gateway metadata seam with Marvex policy authoritative.
- `packages/adapters/capabilities/lmstudio.py`: LM Studio local tool/MCP host proposal seam with Marvex policy and trace ownership retained.
- `packages/adapters/capabilities/skills.py`: skill refs, manifest metadata, validation result, eligibility contribution, no policy override, and no untrusted script execution.
- `packages/adapters/capabilities/integrations.py`: plugin, connector, and integration refs/manifests with auth requirement, data access classification, side-effect classification, and no default secret storage.

## Dependency Decision

The MCP Adapter Foundation now adds `mcp==1.27.1` for official MCP Python SDK protocol mechanics inside `packages.adapters.capabilities.mcp` only. Existing `openai`, `litellm`, and `pydantic` dependency decisions remain valid for their approved boundaries. MCP SDK adoption is narrow: no arbitrary server launch, no registry install, no automatic tool calls, and no runtime turn-flow integration.

LangGraph, LangChain, LlamaIndex, Claude Skills, awesome-harness-engineering, and awesome-context-ai informed the context, planning, skill, and harness vocabulary but do not own Marvex runtime behavior.

## Safety Invariants

- No real shell, filesystem write, browser, OS, email, calendar, account connector, or arbitrary MCP server execution is implemented.
- Fake capability dispatch is deterministic and test-only: permission -> dispatch -> result -> safe summary.
- Context delivery includes only eligible capability projections and bounded excluded reasons. It does not inject all capabilities into every prompt.
- Provider tool calls are proposals and require Marvex permission before any future execution path.
- Raw inputs, raw outputs, raw prompts, provider payloads, credentials, environment variables, and full transcripts are not persisted by default.
- `packages/adapters/capabilities/harness.py`: prompt/context harness manifest seam for schema-summary prompt contributions, context delivery readiness, compaction readiness, and verification hook readiness.
