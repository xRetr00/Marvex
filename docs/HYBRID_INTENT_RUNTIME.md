# Hybrid Intent Runtime

Marvex now routes assistant intent through a hybrid IntentRuntime path instead of treating keyword-only routing as the main runtime behavior.

Runtime path:

1. deterministic safety and shape detectors classify obvious math, unsafe injection, risky actions, freshness requests, browser requests, MCP/tool listings, memory tree requests, connector/account requests, file read/list/search, and clarification cases.
2. Semantic Router builds real local `semantic_router.Route` definitions. No cloud model or hidden API call is made by default.
3. LlamaIndex Core supplies a narrow selector proof through `llama_index.core.selectors.SingleSelection` for route refinement metadata.
4. Capability availability is checked before a route is treated as actionable. Unavailable web search routes clarify instead of hallucinating.
5. Freshness-sensitive prompts set `freshness_needed` and route to web search when available.
6. IntentRuntime returns an `IntentPlan` for composed tasks such as web search plus repo read plus grounded answer.

Supported intents include simple chat, calculator, web search, grounded answer, memory tree, browser, MCP, skill, connector/account, settings/control plane, file read/list/search, risky action, clarification, and unsafe/injection suspicion.

Ownership boundaries:

- IntentRuntime owns route decisions and safe route metadata.
- CapabilityRuntime owns capability permission, approval, and dispatch.
- Semantic Router and LlamaIndex are components only; neither owns policy, prompt assembly, memory, tool dispatch, agent loop, or RuntimeComposition.
- Low-confidence, ambiguous, unavailable, or risky action routes must clarify or require approval rather than auto-act.

Regression gate: `scripts/check_hybrid_intent_web_search_governance.py` proves required examples route through `hybrid_intent_runtime`, not the old deterministic foundation fallback.
