# Library Decision: Intent, Context, and Prompt Harness Foundations

library name: Semantic Router, LlamaIndex routers/selectors, LangChain/LangGraph context engineering, Guardrails AI, OpenAI Agents SDK guardrails, Anthropic context engineering patterns, awesome-harness/context resources

official source: https://semantic-router.readthedocs.io/, https://docs.llamaindex.ai/, https://docs.langchain.com/, https://docs.guardrailsai.com/, https://openai.github.io/openai-agents-python/, https://docs.anthropic.com/, https://www.anthropic.com/engineering, https://github.com/Meirtz/Awesome-Context-Engineering

maintenance status: Active or reference-useful as of 2026-05-18. Semantic Router, LlamaIndex, LangChain/LangGraph, Guardrails AI, and OpenAI Agents SDK are maintained library surfaces. Anthropic context engineering guidance and awesome context/harness lists are reference material, not runtime dependencies.

why use it: Intent routing, selector patterns, context assembly, validation guardrails, and context-compaction practices are established ecosystem surfaces. Marvex should learn from them and keep SDK adoption behind adapters rather than inventing a monolithic harness brain inside Core.

why not custom code: Custom harness machinery would easily become prompt dumping, hidden tool routing, retry loops, or policy ownership in the wrong package. The foundation keeps Marvex-owned safety contracts while creating adapter seams for future maintained backends.

fallback if abandoned: Keep `packages.intent_runtime`, `packages.context_runtime`, `packages.prompt_harness_runtime`, `packages.adapters.intent.harness_semantic_router`, and `packages.adapters.prompt_harness` as stable Marvex boundaries. Future work can adopt, replace, or keep disabled any external backend without moving policy into Core, ProviderRuntime, Local API, Telemetry, or RuntimeComposition.

pyproject dependency: semantic-router

declared dependency: semantic-router==0.1.14

verified date: 2026-05-18

verified by: Codex

scope: Foundation only. No embedding/vector search, no autonomous planner, no generic provider routing, no raw prompt persistence, no browser/computer actions, and no automatic retry loop are adopted.

architecture fit: Good as adapter/reference surfaces, not as authority. CapabilityRuntime remains authoritative for capability policy, permissions, eligibility, dispatch, approvals, and result envelopes. IntentRuntime owns safe intent decisions, ContextRuntime owns context candidates/packs/policy, and PromptHarnessRuntime owns bounded prompt plans assembled from safe projections.

adopt / defer / reject decision:

- Semantic Router: adopted as `semantic-router==0.1.14` behind `packages.adapters.intent.semantic_router_adapter`. Tests use real route definitions with local no-cloud scoring proof only; IntentRuntime remains policy owner.
- LlamaIndex routers/selectors: deferred. Resolver dry-run succeeded for `llama-index==0.14.22`, but the install set includes OpenAI LLM/embedding packages, workflows, SQLAlchemy, NLTK, and broad query/context machinery. That is too broad and not needed until a later context/router selector backend phase.
- LangChain/LangGraph: deferred. Resolver dry-run succeeded for `langgraph==1.2.0` and `langchain==1.3.1`, but the install set includes graph runtime, checkpointing, prebuilt graph helpers, LangSmith, and planning/interrupt primitives. That is runtime-ownership risk and not needed until a later planning/backend phase.
- Guardrails AI: blocked. `python -m pip index versions guardrails-ai` and dry-run install returned no matching distribution for Python 3.12.0 in this environment. Marvex keeps a tested safe projection validator seam and explicit blocked backend reason; Guardrails must not assemble prompts or run retries.
- OpenAI Agents SDK: adopted narrowly as `openai-agents==0.17.2` for compatibility probing only. It maps SDK presence into CapabilityRuntime proposals and cannot own Marvex policy, tools, prompt harness, or agent loop.
- Anthropic context engineering patterns: reference-only now. Adopt the practices of bounded context, compaction, and tool-result clearing as Marvex models, not a runtime dependency.
- awesome-harness-engineering and awesome-context resources: reference-only now for ecosystem awareness; not authoritative specs.

risks: These libraries can own routing, agent loops, tools, retries, prompt mutation, or raw context if adopted directly. Current mitigation is adapter-local SDK use, safe projection-only validation, no raw prompt/context access, no automatic retries, no autonomous loops, blocked broad-framework adoption, and boundary gates.
