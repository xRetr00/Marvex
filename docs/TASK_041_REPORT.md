# Task 041 Report - Decision Runtime Boundary Correction

## Summary

Task 041 removes CLI ownership of decision diagnostics and returns decision
factories to composition-only helpers. Normal CLI provider turns, health, and
version behavior are unchanged.

The `DecisionPipeline` location was reviewed after the CLI and factory cleanup.
It remains in the existing adapter path for this task because the new boundary
checks pass and no remaining responsibility violation requires a move.

## Changed Files

- `apps/cli/main.py`
- `apps/cli/README.md`
- `packages/decision_runtime/decision_pipeline_factory.py`
- `packages/decision_runtime/decision_preflight_factory.py`
- `packages/adapters/policy/pycasbin_policy_adapter.py`
- `scripts/check_decision_runtime_boundaries.py`
- `scripts/run_all_checks.py`
- `tests/api/test_cli_decision_dry_run.py`
- `tests/api/test_cli_preflight_core_adjacent.py`
- `tests/api/test_cli_preflight_observe.py`
- `tests/intent/test_policy_gate_adapter.py`
- `tests/pipeline/test_decision_pipeline_boundaries.py`
- `docs/MODULE_INDEX.md`
- `docs/TASK_041_REPORT.md`

## Boundary Result

- CLI no longer imports `packages.decision_runtime`.
- CLI no longer exposes `decision-dry-run` or `--decision-preflight`.
- Factories no longer contain dev router/validator/policy components.
- Factories no longer perform payload/report shaping.
- Policy no longer owns route ambiguity clarification.
- A decision runtime boundary check is included in `run_all_checks.py`.

## Non-Goals Preserved

- No provider logic changes.
- No Core orchestration changes.
- No new dependencies.
- No new runtime facade or system.
- No blocking behavior added.
