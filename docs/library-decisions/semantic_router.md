# Library Decision: Semantic Router

library name: Semantic Router

official source: https://github.com/aurelio-labs/semantic-router and https://docs.aurelio.ai/

maintenance status: Active as of April 29, 2026. PyPI latest version observed as 0.1.12. The GitHub README describes Semantic Router as a fast decision-making layer for LLMs and agents using semantic vector routing instead of slow LLM generations.

why use it: Marvex needs a maintained component for intent pre-routing and route-family selection before any tool or context exposure. Semantic Router fits that role better than a hand-written phrase router because it routes by semantic similarity and can stay behind a thin Marvex boundary.

why not custom code: Custom routing would recreate embedding selection, route calibration, route persistence, score thresholds, and evaluation behavior. Vaxil already showed that custom cue lists turn into special-case routing authority. Marvex should reject phrase-list routing as architecture and defer any homegrown intent framework until a maintained library has clearly failed behind an adapter.

fallback if abandoned: Keep the Marvex route-family boundary small enough to replace Semantic Router with another maintained semantic router, a provider-native classifier, or a tiny local validator model through a new library decision task.

pyproject dependency: none in Task 033

declared dependency: not declared; Task 033 must not edit pyproject.toml

verified date: 2026-04-29

verified by: Codex

scope: Candidate only. Future use must be limited to intent pre-routing behind a thin adapter/port boundary. It must not become a central runtime, smart controller, tool runtime, memory runtime, or agent framework.

architecture fit: Good for the first route-family decision: `direct_answer`, `grounded_lookup`, `local_state_inspection`, and `clarify`. It should return a route family and score only. Marvex policy, context, and dispatch must remain separate.

adopt / defer / reject decision: Adopt as the preferred ready library for Task 034 evaluation behind a thin Marvex adapter boundary. Do not integrate directly into Core and do not expose tools from the router result.

risks: Embedding choice and thresholds can drift. Route labels can become hidden policy if not audited. Local-only routing may need optional extras. Semantic similarity can still misroute ambiguous input, so a validator layer remains required.

comparison to custom routing: Library-backed routing is preferred because it makes route scoring a replaceable component. Custom deterministic routing is deferred to test fixtures and emergency fallback only. Phrase-list routing is explicitly rejected as an architectural strategy.
