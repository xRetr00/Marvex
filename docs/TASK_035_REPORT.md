# Task 035 Report - Context Builder Contract Slice

## Summary

Task 035 adds a narrow, route-driven context builder contract slice. It produces declarative prompt block plans and assembly reports from user input, `IntentDecision`, and `PolicyDecision`.

This slice does not render prompt strings, call providers, expose tools, retrieve memory, use MCP, or add model validation.

## Changed Files

- `packages/contracts/prompt_plan_models.py`
- `packages/ports/context_builder_port.py`
- `packages/adapters/context/context_builder.py`
- `tests/context/test_prompt_plan_contracts.py`
- `tests/context/test_context_builder.py`
- `tests/context/test_prompt_budget_enforcement.py`
- `docs/TASK_035_REPORT.md`

## Contracts Added

- `PromptBlockType` fails closed to the approved block set: identity, user input, verified evidence, selected memory, selected tools, and response contract.
- `PromptBlock` requires explicit content, reason code, character budget, and inclusion state.
- `PromptPlan` is declarative only, enforces total budget, and rejects non-empty tool exposure.
- `PromptAssemblyReport` records included blocks, suppressed blocks, reason codes, and budget used.
- Future tool surface categories are documented as inert contract metadata only: provider built-in tools, MCP server tools, local function tools, desktop actions, and browser actions.

## Behavior Added

- `direct_answer` plans include identity, budgeted user input, and response contract blocks.
- `clarify` plans retain only redacted clarification evidence, never full raw input.
- `local_state_inspection` and `grounded_lookup` receive route-specific response contracts.
- Evidence, memory, and tool blocks are suppressed placeholders by default.
- Over-budget user input is suppressed instead of expanding prompt budget.
- `tool_surface_exposed` remains empty in Task 035, and no tool catalog or provider-specific built-in tool schema enters `PromptPlan`.

## Validation

Completed validation:

- `python -m pytest tests/context/test_prompt_plan_contracts.py tests/context/test_context_builder.py tests/context/test_prompt_budget_enforcement.py` - 15 passed
- `python -m pytest` - 154 passed, 1 skipped
- `python scripts/run_all_checks.py` - passed
- `git status --short` - only Task 035 files changed

## Risks

- The builder currently uses fixed budgets. Task 036 or later runtime wiring may need externally configured budgets, but that should stay outside this contract slice.
- `PromptPlan` intentionally contains block content, not a rendered provider prompt. Any future prompt renderer must consume only included blocks and preserve budget reporting.
- Tool exposure is rejected in this slice. Future tool planning must extend the contract deliberately rather than reusing prompt blocks as a tool catalog.
- The documented future categories are not an adoption decision for MCP or provider built-in tools. They only prevent future design from assuming MCP is the sole tool source.

## Proposed Task 036 Scope

Tiny intent validator model slice using an LFM2.5-350M-class model or justified equivalent behind a thin validation adapter. It should validate existing route and context decisions only, with no agent runtime, tool routing, prompt rendering, or provider orchestration.
