# Task 040 Report - Core-Adjacent Decision Preflight Observe Mode

## Summary

Task 040 adds a dedicated turn preflight boundary around the existing decision pipeline and updates the CLI preflight path to use that boundary instead of calling the raw decision pipeline helper.

This slice remains observe-only. Provider execution is never blocked, prompts are not rendered, tools/MCP/memory are not executed, and Core orchestration is unchanged.

## Changed Files

- `packages/contracts/turn_preflight_models.py`
- `packages/ports/turn_preflight_port.py`
- `packages/adapters/preflight/decision_preflight_adapter.py`
- `packages/decision_runtime/decision_preflight_factory.py`
- `apps/cli/main.py`
- `tests/preflight/test_turn_preflight_contracts.py`
- `tests/preflight/test_decision_preflight_adapter.py`
- `tests/api/test_cli_preflight_core_adjacent.py`
- `tests/api/test_cli_preflight_observe.py`
- `docs/TASK_040_REPORT.md`

## Validation Result

Completed validation:

- `python -m pytest tests/preflight/test_turn_preflight_contracts.py tests/preflight/test_decision_preflight_adapter.py tests/api/test_cli_preflight_core_adjacent.py` - 14 passed
- `python -m pytest` - 200 passed, 1 skipped
- `python scripts/run_all_checks.py` - passed
- `git status --short` - only Task 040 files changed

## Risks

- The preflight boundary still uses dev-only deterministic decision pipeline components through the factory. Task 041 should replace those with configurable library-backed observe-mode wiring.
- CLI output shape changed from the Task 039 `decision_preflight` wrapper to the Task 040 `turn_preflight` boundary wrapper. Existing Task 039 tests were updated to reflect the new boundary.
- Blocking behavior remains explicitly out of scope. Any future blocking/clarify behavior needs a separate approval and config path.

## Proposed Task 041 Scope

Replace dev-only deterministic pipeline components with library-backed configurable components for observe mode, starting with Semantic Router adapter wiring while keeping provider execution unblocked.
