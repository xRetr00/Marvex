# Task 033 Report: Intent and Runtime Library Decision Spike

## Adopt Now

- Semantic Router: adopt as the preferred ready library for future intent pre-routing behind a thin Marvex adapter/port boundary. It may return only route family plus score, not tools or policy.
- PyCasbin: adopt as the preferred lightweight policy-engine candidate for future capability checks after policy contracts exist.

## Defer

- LiquidAI LFM2.5-350M: defer until a model runtime decision approves how Marvex runs tiny local validators. It is promising for route validation and structured extraction, but Task 033 must not add model runtime.
- Official MCP Python SDK: defer implementation, but use the official SDK when an approved MCP task exists. No MCP runtime is built in Task 033.
- Outlines: defer as a future constrained-output option for local models after provider/model runtime decisions.

## Reject

- Pydantic AI as a central Marvex runtime: reject for now because it is an agent framework and would violate the framework gravity rule. It may be reconsidered only for isolated experiments.
- Phrase-list routing as architecture: reject. It caused Vaxil-style special-case growth and hidden routing authority.
- Homegrown intent framework: reject/defer. Marvex should first evaluate maintained library-backed routing and validators behind thin boundaries.

## Spike Findings

- `tests/spikes/test_semantic_router_spike.py` proves a route decision can stay limited to one route family: `direct_answer`, `grounded_lookup`, `local_state_inspection`, or `clarify`.
- The semantic-router spike proves route selection does not expose broad tools. The decision shape carries `exposed_tools=()`.
- If `semantic_router` is installed, the spike performs a minimal `Route` constructor smoke path. If absent, only that import smoke is skipped.
- `tests/spikes/test_structured_intent_validation_spike.py` proves Pydantic can validate a toy structured intent result with extra-field rejection, route enum rejection, and low-confidence clarification handling.
- Custom deterministic routing appears only as a rejected test baseline. The spike records that custom routing becomes phrase-list policy and is not an architecture choice.

## Risks

- Semantic routing still needs calibration, replay fixtures, and a validator layer. Similarity scores must not silently become policy.
- Tiny validators can be overconfident and must not answer questions or dispatch tools.
- MCP SDK adoption must wait for policy gates, allowlists, and worker boundaries because MCP discovery is not the same as safe tool exposure.
- PyCasbin policies can become hidden authority unless generated from explicit Marvex policy contracts.
- Pydantic AI and similar frameworks can pull Marvex toward framework-owned agent runtime, which is explicitly out of scope.

## Proposed Task 034

Adopt selected ready library behind a thin Marvex adapter/port boundary plus tests; no custom intent runtime skeleton.

Task 034 should use Semantic Router only as a component-level pre-routing adapter candidate. It must not implement tools, MCP runtime, memory, agent runtime, smart controller behavior, phrase routing, or a homegrown intent framework.
