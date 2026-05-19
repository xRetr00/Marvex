# Library Decision: Semantic Router

library name: Semantic Router

official source: https://github.com/aurelio-labs/semantic-router and https://docs.aurelio.ai/

maintenance status: Active as of May 19, 2026. uv resolved `semantic-router[hybrid]==0.1.14`; uv reported that this package version does not provide a `hybrid` extra, so Marvex keeps the base package and implements a hybrid-compatible fallback using real `semantic_router.Route` definitions plus Marvex-owned scoring and selector logic.

why use it: Marvex needs a maintained component for intent pre-routing and route-family selection before any tool or context exposure. Semantic Router fits that role better than a hand-written phrase router because it routes by semantic similarity and can stay behind a thin Marvex boundary.

why not custom code: Custom routing would recreate embedding selection, route calibration, route persistence, score thresholds, and evaluation behavior. Vaxil already showed that custom cue lists turn into special-case routing authority. Marvex should reject phrase-list routing as architecture and defer any homegrown intent framework until a maintained library has clearly failed behind an adapter.

fallback if abandoned: Keep the Marvex route-family boundary small enough to replace Semantic Router with another maintained semantic router, a provider-native classifier, or a tiny local validator model through a new library decision task.

pyproject dependency: semantic-router

declared dependency: semantic-router[hybrid]==0.1.14

verified date: 2026-05-19

verified by: Codex

scope: Adopted behind both `packages.adapters.intent.semantic_router_adapter` and the Marvex-owned hybrid `packages.intent_runtime.hybrid` path. The runtime builds real `semantic_router.Route` definitions locally with no cloud/API call by default, then lets IntentRuntime own policy, capability availability, clarification, and route decisions. It must not become a central runtime, smart controller, policy owner, tool runtime, memory runtime, or agent framework.

architecture fit: Good for the first route-family decision: `direct_answer`, `grounded_lookup`, `local_state_inspection`, and `clarify`. It should return a route family and score only. Marvex policy, context, and dispatch must remain separate.

adopt / defer / reject decision: Adopt. The package is declared in `pyproject.toml` with the attempted hybrid extra. Tests prove real route definitions can be built, required examples route through `hybrid_intent_runtime`, low-confidence/unknown input falls back to clarification, and the hybrid-extra absence is surfaced in safe runtime details. Do not integrate directly into Core and do not expose tools from the router result.

risks: Embedding choice and thresholds can drift. Route labels can become hidden policy if not audited. Local-only routing may need optional extras. Semantic similarity can still misroute ambiguous input, so IntentRuntime policy and clarification fallback remain required. Current tests avoid hidden model/API calls by using local route objects and Marvex-owned scoring proof only.

comparison to custom routing: Library-backed routing is preferred because it makes route scoring a replaceable component. Custom deterministic routing is deferred to test fixtures and emergency fallback only. Phrase-list routing is explicitly rejected as an architectural strategy.
