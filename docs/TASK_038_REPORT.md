# Task 038 Report - CLI Decision Pipeline Dry-Run Command

## Summary

Task 038 adds a CLI-only developer dry-run command that invokes the decision pipeline and prints structured JSON output.

This slice does not execute providers, render prompts, execute tools, use MCP, retrieve memory, or change Core orchestration.

## Changed Files

- `apps/cli/main.py`
- `packages/decision_runtime/decision_pipeline_factory.py`
- `tests/api/test_cli_decision_dry_run.py`
- `docs/TASK_038_REPORT.md`

## Validation Result

Completed validation:

- `python -m pytest tests/api/test_cli_decision_dry_run.py` - 5 passed
- `python -m pytest` - 181 passed, 1 skipped
- `python scripts/run_all_checks.py` - passed
- `git status --short` - only Task 038 files changed

## Risks

- The dry-run path uses deterministic dev-only components. It is useful for inspection, not production route quality.
- The output intentionally summarizes prompt plans without block content. Future debugging may need a separate approved verbose mode.
- Task 039 must keep observe/report mode separate from blocking provider execution.

## Proposed Task 039 Scope

Wire DecisionPipeline into existing CLI turn path as observe/report preflight before provider calls, still without blocking provider execution by default.
