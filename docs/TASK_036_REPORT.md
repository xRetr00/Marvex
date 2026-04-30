# Task 036 Report - Tiny Intent Validator Adapter Slice

## Summary

Task 036 adds a thin intent validation boundary for a tiny LFM2.5-350M-class validator. The slice validates `IntentDecision` quality through an injected model client and returns a typed `IntentValidationResult`.

This slice does not answer user questions, render prompts, add tools, use MCP, retrieve memory, change Core orchestration, or introduce a custom validator framework.

## Changed Files

- `packages/contracts/intent_validation_models.py`
- `packages/ports/intent_validator_port.py`
- `packages/adapters/intent/tiny_intent_validator_adapter.py`
- `tests/intent/test_intent_validation_contracts.py`
- `tests/intent/test_tiny_intent_validator_adapter.py`
- `docs/TASK_036_REPORT.md`

## Validation Result

Completed validation:

- `python -m pytest tests/intent/test_tiny_intent_validator_adapter.py tests/intent/test_intent_validation_contracts.py` - 12 passed
- `python -m pytest` - 166 passed, 1 skipped
- `python scripts/run_all_checks.py` - passed
- `git status --short` - only Task 036 files changed

## Risks

- The optional real-runtime constructor intentionally does not wire a local inference stack yet. It reports structured unavailability instead of adding an undeclared dependency.
- Tiny-model validation can still be wrong or overconfident. Future work needs replay fixtures before it can influence production routing automatically.
- The validator boundary must stay advisory. It must not become a hidden router, controller, prompt renderer, or tool dispatcher.

## Proposed Task 037 Scope

Integrate route decision + intent validation + policy decision + context builder behind a thin composition boundary with tests, still without Core orchestration changes, prompt rendering, tools, MCP, or memory.
