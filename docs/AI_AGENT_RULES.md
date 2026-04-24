# AI Agent Rules

This project will be built by AI coding agents. The user is not expected to verify code correctness manually.

## Required Before Work

Every task starts with a task spec.

The agent must identify:

- goal
- allowed files
- forbidden files
- contracts touched
- tests required
- validation scripts required
- rollback plan

## Implementation Rules

- One slice only.
- No "fix all bugs" prompts.
- No unrelated edits.
- No architecture changes during bug fixes.
- No implementation before docs are accepted.
- No feature before contract.
- No provider logic in Core.
- No UI logic in Core.
- No tool execution in UI.
- No giant orchestrator.

## Validation Rules

Every change must include:

- tests appropriate to the change
- `python scripts/run_all_checks.py`
- final report with changed files and risks

## Reporting Rules

Final report must include:

- task id
- changed files
- tests run
- validation result
- risks
- deferred work

## Stop Conditions

The agent must stop and report instead of coding if:

- the task has no approved contract
- the task requires a forbidden v1 module
- the task would create a god object
- the task requires custom SDK code while a maintained SDK may exist
- the task edits unrelated files

