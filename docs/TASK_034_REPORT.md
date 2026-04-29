# Task 034 Report: Semantic Router Adapter Adoption Slice

## Changed Files

- `packages/contracts/intent_models.py`
- `packages/ports/intent_router_port.py`
- `packages/ports/policy_gate_port.py`
- `packages/adapters/intent/semantic_router_adapter.py`
- `packages/adapters/policy/pycasbin_policy_adapter.py`
- `packages/provider_runtime/intent_adapter_factory.py`
- `tests/intent/test_semantic_router_adapter.py`
- `tests/intent/test_policy_gate_adapter.py`
- `tests/intent/test_route_policy_integration.py`
- `scripts/check_forbidden_modules.py`
- `docs/library-decisions/semantic_router.md`
- `docs/library-decisions/policy_engine.md`
- `docs/TASK_034_REPORT.md`

## Adapter Boundaries Added

- Semantic Router boundary: `SemanticRouterAdapter` wraps an injected Semantic Router-compatible route layer and returns only `IntentDecision`.
- PyCasbin boundary: `PyCasbinPolicyAdapter` wraps an injected enforcer and returns only `PolicyDecision`.
- Ports: `IntentRouterPort` and `PolicyGatePort` define minimal method signatures only.
- Factory: `intent_adapter_factory.py` composes injected adapter dependencies only. It does not import Core, providers, tools, MCP, memory, prompts, or agents.

## Tests Run

- `python -m pytest tests/intent/test_semantic_router_adapter.py tests/intent/test_policy_gate_adapter.py tests/intent/test_route_policy_integration.py`
- `python -m pytest`
- `python scripts/run_all_checks.py`

## Validation Result

Validation passed for targeted Task 034 tests, full pytest suite, and Marvex validation gates.

## Risks

- `semantic_router` and `casbin` are not declared dependencies yet, so real-library constructors report structured dependency-unavailable errors when packages are absent.
- Route-family confidence thresholds still need replay calibration.
- PyCasbin policy content is not introduced yet; future policy files must not become hidden routing authority.
- Task 034 does not include a tiny model validator. Ambiguity handling remains route-score based only.

## Proposed Task 035 Scope

Task 035 should evaluate and adopt a tiny intent validator model slice for an LFM2.5-350M-class local validator. It should validate route confidence and ambiguity only, remain behind a thin boundary, and must not answer questions, execute tools, build prompts, or become an agent runtime.
