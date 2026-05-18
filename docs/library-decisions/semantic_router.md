# Library Decision: Semantic Router

library name: Semantic Router

official source: https://github.com/aurelio-labs/semantic-router and https://docs.aurelio.ai/

maintenance status: Active as of May 18, 2026. Dependency audit resolved `semantic-router==0.1.14` on Python 3.12.0 with the current Marvex dependency set after the safe OpenAI/LiteLLM compatibility upgrade.

why use it: Marvex needs a maintained component for intent pre-routing and route-family selection before any tool or context exposure. Semantic Router fits that role better than a hand-written phrase router because it routes by semantic similarity and can stay behind a thin Marvex boundary.

why not custom code: Custom routing would recreate embedding selection, route calibration, route persistence, score thresholds, and evaluation behavior. Vaxil already showed that custom cue lists turn into special-case routing authority. Marvex should reject phrase-list routing as architecture and defer any homegrown intent framework until a maintained library has clearly failed behind an adapter.

fallback if abandoned: Keep the Marvex route-family boundary small enough to replace Semantic Router with another maintained semantic router, a provider-native classifier, or a tiny local validator model through a new library decision task.

pyproject dependency: semantic-router

declared dependency: semantic-router==0.1.14

verified date: 2026-05-18

verified by: Codex

scope: Adopted behind `packages.adapters.intent.semantic_router_adapter`. `SemanticRouterAdapter` builds real `semantic_router.Route` definitions and maps a local no-cloud route-layer proof into Marvex `IntentDecision`. It must not become a central runtime, smart controller, policy owner, tool runtime, memory runtime, or agent framework.

architecture fit: Good for the first route-family decision: `direct_answer`, `grounded_lookup`, `local_state_inspection`, and `clarify`. It should return a route family and score only. Marvex policy, context, and dispatch must remain separate.

adopt / defer / reject decision: Adopt. The package is declared in `pyproject.toml`; tests prove real route definitions can be built, known input maps to a route, and low-confidence/unknown input falls back to `clarify`. Do not integrate directly into Core and do not expose tools from the router result.

risks: Embedding choice and thresholds can drift. Route labels can become hidden policy if not audited. Local-only routing may need optional extras. Semantic similarity can still misroute ambiguous input, so IntentRuntime policy and clarification fallback remain required. Current tests avoid hidden model/API calls by using local route objects and Marvex-owned scoring proof only.

comparison to custom routing: Library-backed routing is preferred because it makes route scoring a replaceable component. Custom deterministic routing is deferred to test fixtures and emergency fallback only. Phrase-list routing is explicitly rejected as an architectural strategy.
