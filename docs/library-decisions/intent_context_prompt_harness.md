# Library Decision: Intent, Context, and Prompt Harness Foundations

library name: Semantic Router, LlamaIndex routers/selectors, LangChain/LangGraph context engineering, Guardrails AI, OpenAI Agents SDK guardrails, Anthropic context engineering patterns, awesome-harness/context resources

official source: https://semantic-router.readthedocs.io/, https://docs.llamaindex.ai/, https://docs.langchain.com/, https://docs.guardrailsai.com/, https://openai.github.io/openai-agents-python/, https://docs.anthropic.com/, https://www.anthropic.com/engineering, https://github.com/Meirtz/Awesome-Context-Engineering

maintenance status: Active or reference-useful as of 2026-05-18. Semantic Router, LlamaIndex, LangChain/LangGraph, Guardrails AI, and OpenAI Agents SDK are maintained library surfaces. Anthropic context engineering guidance and awesome context/harness lists are reference material, not runtime dependencies.

why use it: Intent routing, selector patterns, context assembly, validation guardrails, and context-compaction practices are established ecosystem surfaces. Marvex should learn from them and keep SDK adoption behind adapters rather than inventing a monolithic harness brain inside Core.

why not custom code: Custom harness machinery would easily become prompt dumping, hidden tool routing, retry loops, or policy ownership in the wrong package. The foundation keeps Marvex-owned safety contracts while creating adapter seams for future maintained backends.

fallback if abandoned: Keep `packages.intent_runtime`, `packages.context_runtime`, `packages.prompt_harness_runtime`, `packages.adapters.intent.harness_semantic_router`, and `packages.adapters.prompt_harness` as stable Marvex boundaries. Future work can adopt, replace, or keep disabled any external backend without moving policy into Core, ProviderRuntime, Local API, Telemetry, or RuntimeComposition.

pyproject dependency: none

declared dependency: none

verified date: 2026-05-18

verified by: Codex

scope: Foundation only. No embedding/vector search, no autonomous planner, no generic provider routing, no raw prompt persistence, no browser/computer actions, and no automatic retry loop are adopted.

architecture fit: Good as adapter/reference surfaces, not as authority. CapabilityRuntime remains authoritative for capability policy, permissions, eligibility, dispatch, approvals, and result envelopes. IntentRuntime owns safe intent decisions, ContextRuntime owns context candidates/packs/policy, and PromptHarnessRuntime owns bounded prompt plans assembled from safe projections.

adopt / defer / reject decision:

- Semantic Router: create adapter seam now with disabled/proof backend. Defer package adoption until an embedding/encoder decision exists.
- LlamaIndex routers/selectors: adapter seam/reference now through prompt harness external seams. Defer runtime dependency; avoid importing query engine behavior before Marvex has stable context source contracts.
- LangChain/LangGraph: adapter seam/reference now. Defer dependency; do not import agent loops, middleware, interrupts, or planner ownership into this foundation.
- Guardrails AI: create validation adapter seam now with disabled backend. Defer runtime dependency; Marvex validates safe projections and avoids automatic retry loops.
- OpenAI Agents SDK: adapter seam/reference now. Defer dependency because Marvex must not let provider SDK tool/context patterns bypass CapabilityRuntime policy.
- Anthropic context engineering patterns: reference-only now. Adopt the practices of bounded context, compaction, and tool-result clearing as Marvex models, not a runtime dependency.
- awesome-harness-engineering and awesome-context resources: reference-only now for ecosystem awareness; not authoritative specs.

risks: These libraries can own routing, agent loops, tools, retries, prompt mutation, or raw context if adopted directly. Current mitigation is disabled/proof backends, safe projection-only validation, no raw prompt/context access, no automatic retries, no autonomous loops, and boundary gates.
