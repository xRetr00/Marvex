# Task 039 Report - CLI Turn Preflight Observe Mode

## Summary

Task 039 adds `--decision-preflight` to the normal CLI turn path. When enabled, the CLI prints a summarized JSON decision preflight report before provider execution and then continues the provider call normally.

This slice does not block provider execution, render prompts, execute tools, use MCP, retrieve memory, or change Core orchestration.

## Changed Files

- `apps/cli/main.py`
- `tests/api/test_cli_preflight_observe.py`
- `docs/TASK_039_REPORT.md`

## Validation Result

Completed validation:

- `python -m pytest tests/api/test_cli_preflight_observe.py` - 5 passed
- `python -m pytest` - 186 passed, 1 skipped
- `python scripts/run_all_checks.py` - passed
- `git status --short` - only Task 039 files changed

## Risks

- The preflight path uses deterministic dev-only pipeline components. It is an inspection signal, not production-quality routing.
- The preflight report is printed before provider output, so downstream CLI consumers must account for the extra JSON line only when the flag is enabled.
- Blocking behavior remains explicitly out of scope. A later task must decide whether clarify/deny should ever affect provider execution.

## Proposed Task 040 Scope

Implement Core-adjacent decision preflight integration in observe-only mode behind an explicit config/flag, still without blocking provider execution by default.
