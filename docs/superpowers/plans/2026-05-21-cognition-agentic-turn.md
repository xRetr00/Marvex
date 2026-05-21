# Cognition Agentic Turn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Cognition Runtime and bounded Agentic Turn Loop so live Core turns assemble intent, context, memory, prompt, evidence, policy, tools, provider calls, telemetry, and final responses through Assistant OS boundaries.

**Architecture:** `packages/cognition_runtime` owns pure planning and safe projections. `services/core` owns subprocess worker IPC, bounded loop execution, approval pause/resume, and provider/tool/web execution. Existing intent/context/prompt/memory/web/grounded/capability runtimes remain authoritative behind clean boundaries.

**Tech Stack:** Python, Pydantic, uv, existing JSONL workers, existing telemetry, existing provider/web/search/grounding runtimes.

---

### Task 1: RED Tests

**Files:**
- Create: `tests/cognition_runtime/test_cognition_runtime.py`
- Create: `tests/core/test_core_agentic_turn_loop.py`
- Modify: `tests/core/test_core_intent_tool_worker_integration.py`

- [ ] Add tests proving cognition assembly returns intent, context, prompt, step plan, evidence requirements, and safe projections.
- [ ] Add Core CLI tests proving bounded loop metadata, grounded search/validated citations, no-evidence clarification, real safe calculator result, and approval pause/resume.
- [ ] Run targeted tests with `uv run python -m pytest ...` and confirm they fail for missing behavior.

### Task 2: Cognition Runtime

**Files:**
- Create: `packages/cognition_runtime/__init__.py`
- Create: `packages/cognition_runtime/models.py`
- Create: `packages/cognition_runtime/runtime.py`
- Test: `tests/cognition_runtime/test_cognition_runtime.py`

- [ ] Implement pure models for cognition input, step plan, evidence refs, and safe projection.
- [ ] Implement `CognitionRuntime.assemble_turn()` using `classify_intent`, `HybridIntentRuntime.plan`, `build_context_pack`, `assemble_prompt_harness`, memory reads, memory-tree refs, and optional injected web evidence.
- [ ] Keep imports pure: no subprocess, providers, adapters, worker internals, raw persistence, or file writes.

### Task 3: Core Bounded Loop

**Files:**
- Modify: `services/core/main.py`
- Test: `tests/core/test_core_agentic_turn_loop.py`

- [ ] Add a small max-step cap and loop guard around plan/act/observe/finalize.
- [ ] Preserve existing `_ProviderWorkerProcessProvider`, `_IntentWorkerProcessClassifier`, and `_ToolWorkerProcessExecutor` IPC pattern.
- [ ] Emit safe telemetry events under one trace id and return AssistantTurnResult metadata containing loop projection and cognition safe projection.

### Task 4: Grounding Enforcement

**Files:**
- Modify: `services/core/main.py`
- Modify: `packages/cognition_runtime/runtime.py`
- Test: `tests/core/test_core_agentic_turn_loop.py`

- [ ] For `WEB_SEARCH`/`GROUNDED_ANSWER`, run web search without asking when freshness/grounding is required.
- [ ] Build final answer only from evidence refs and validate citations with `validate_grounded_citations`.
- [ ] Return an evidence-missing clarification instead of fabricating when evidence is unavailable.

### Task 5: Tool Result and Approval Resume

**Files:**
- Modify: `services/core/main.py`
- Modify: `services/tool_worker/controller.py`
- Test: `tests/core/test_core_agentic_turn_loop.py`
- Test: `tests/tool_worker/test_tool_worker.py`

- [ ] Return real calculator output from the ToolWorker safe result instead of canned text.
- [ ] Pause risky actions with a structured approval request containing trace id and pending action.
- [ ] Add a runnable Core CLI resume path for approve/deny/cancel and ensure approved resumes execute the same logical turn through the worker boundary.

### Task 6: Gates and Docs

**Files:**
- Create: `scripts/check_cognition_runtime_boundaries.py`
- Create: `scripts/check_core_agentic_turn_loop_boundaries.py`
- Modify: `scripts/run_all_checks.py`
- Modify: `docs/VALIDATION_GATES.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/GOVERNANCE_CLASSIFICATION.md`
- Modify: `PROJECT_STATUS.md`

- [ ] Enforce cognition purity, bounded loop constants/guard, grounding no-fabrication path, no policy bypass, no raw persistence, and packages/core cleanliness.
- [ ] Preserve existing required marker phrases in status and governance docs.

### Task 7: Runtime Smokes, Validation, Commits

**Files:**
- Create or modify runtime smoke docs/scripts only if needed.

- [ ] Run targeted tests after each stage.
- [ ] Run `uv run python scripts/run_all_checks.py` and confirm `PASS all validation checks passed`.
- [ ] Run non-CI smokes for bounded loop, grounded fresh turn, no-evidence turn, safe tool turn, approval approve/deny/cancel, and real provider/web when reachable.
- [ ] Commit completed stages. Attempt push; if push fails, continue and include manual commit/push note in the final report.
