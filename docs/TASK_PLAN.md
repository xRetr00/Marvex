# Task Plan

## Global Task Rules

Planning tasks may edit only docs, templates, diagrams, placeholder READMEs, and validation scripts.

Normal small and medium tasks must follow `docs/GIT_RULES.md` and run directly
on `main`.

The required task flow is plan, user approval, implementation, validation,
commit to `main`, push `main`, and only then the next task.

Agents must not create branches automatically. Branches require user approval
first and are limited to large subsystems, risky refactors, or explicitly
approved cases.

Agents must not start Task N+1 while Task N has uncommitted changes.

Tags may be created only after validation passes and the user approves, or when
a milestone clearly requires the tag.

Implementation tasks require:

- `PROJECT_STATUS.md` with `accepted_docs: true`
- a real task spec file, not only a task id
- approved contracts in `docs/CONTRACT_APPROVALS.md`
- explicit allowed and forbidden files
- ownership boundary and anti-god-object answers
- tests and validation commands
- rollback plan and final report format

## 1. Create architecture docs.

Goal: Establish the architecture decision, system boundaries, and v1 scope.

Allowed files: `README.md`, `docs/ARCHITECTURE.md`, `docs/PROCESS_MODEL.md`, `docs/diagrams/*`.

Forbidden files: product source files, service implementation files.

Required tests/checks: `python scripts/run_all_checks.py` after validation scripts exist.

Acceptance criteria: Architecture docs define Core Service first, CLI first, future Qt Shell, and v1 forbidden modules.

Failure conditions: Any product implementation is added.

Required final report format: changed files, validation result, risks.

## 2. Create contracts docs.

Goal: Define stable JSON contracts before implementation.

Allowed files: `docs/CONTRACTS.md`, `templates/ERROR_ENVELOPE.md`, `templates/TRACE_EVENT.md`, `templates/CONTRACT_CHANGE.md`.

Forbidden files: product source files, generated SDKs.

Required tests/checks: contract documentation review and `python scripts/run_all_checks.py`.

Acceptance criteria: Required contracts are documented with purpose, fields, owner, readers, and writers.

Failure conditions: Any feature uses an undocumented contract.

Required final report format: changed files, validation result, contract risks.

## 3. Create AI agent rules.

Goal: Define strict rules for future AI coding agents.

Allowed files: `docs/AI_AGENT_RULES.md`, `templates/TASK_SPEC.md`, `templates/AGENT_FINAL_REPORT.md`.

Forbidden files: product source files.

Required tests/checks: `python scripts/run_all_checks.py`.

Acceptance criteria: Rules block implementation before accepted docs and require validation for every task.

Failure conditions: Rules allow vague multi-feature work.

Required final report format: changed files, validation result, risks.

## 4. Create process, IPC, telemetry, library, and validation docs.

Goal: Define service process expectations, IPC APIs, trace lifecycle, library policy, and validation gates.

Allowed files: `docs/PROCESS_MODEL.md`, `docs/IPC_API.md`, `docs/TELEMETRY.md`, `docs/LIBRARY_POLICY.md`, `docs/VALIDATION_GATES.md`, `docs/SUBPROCESS_RULES.md`.

Forbidden files: product source files, dependency lock files.

Required tests/checks: `python scripts/run_all_checks.py`.

Acceptance criteria: Docs define health, version, trace_id, structured logs, error envelope, and library decision requirements.

Failure conditions: Custom implementation is recommended without library research.

Required final report format: changed files, validation result, unresolved decisions.

## 5. Create project skeleton.

Goal: Create directories and README-only placeholders.

Allowed files: placeholder `README.md` files under `services`, `apps`, `packages`, and `tests`.

Forbidden files: non-README files in service placeholders.

Required tests/checks: `python scripts/run_all_checks.py`.

Acceptance criteria: Required folder tree exists and service placeholders are README-only.

Failure conditions: Source files or configs appear in service placeholders.

Required final report format: changed files, validation result, placeholder status.

## 6. Add contracts only.

Goal: Add implementation-neutral contract definitions after docs are accepted.

Allowed files: contract package files approved by contract task spec and `docs/CONTRACT_APPROVALS.md`.

Forbidden files: provider adapters, Core behavior, CLI behavior, UI, tools, memory.

Required tests/checks: contract tests, schema tests, `python scripts/run_all_checks.py`.

Acceptance criteria: Contracts can be validated without running product behavior.

Failure conditions: Contracts include business logic or provider-specific logic.

Required final report format: changed files, tests, validation result, contract risks.

## 7. Add fake provider.

Goal: Add a deterministic fake provider behind the provider port.

Allowed files: approved adapter and tests only, as named by a real task spec.

Forbidden files: Core policy changes, LM Studio code, UI, tools, memory.

Required tests/checks: fake provider tests, contract tests, `python scripts/run_all_checks.py`.

Acceptance criteria: Fake provider returns deterministic `ProviderResponse`.

Failure conditions: Fake provider bypasses provider contracts.

Required final report format: changed files, tests, validation result, risks.

## 8. Add Python Core Service.

Goal: Add minimal Core Service turn orchestration through the provider interface.

Allowed files: approved Core files, Core tests, API tests, as named by a real task spec.

Forbidden files: UI, tools, memory, voice, desktop context, provider-specific Core branches.

Required tests/checks: fake adapter tests, Core turn tests, API tests, `python scripts/run_all_checks.py`.

Acceptance criteria: Core accepts `TurnInput`, calls provider port, returns `TurnOutput`.

Failure conditions: Core imports provider-specific implementation or grows into a god object.

Required final report format: changed files, tests, validation result, Core risks.

## 9. Add telemetry trace lifecycle.

Goal: Add structured trace lifecycle events for v1 turn flow.

Allowed files: telemetry package, Core telemetry integration, telemetry tests, as named by a real task spec.

Forbidden files: unrelated feature modules.

Required tests/checks: trace lifecycle tests, error trace tests, `python scripts/run_all_checks.py`.

Acceptance criteria: Each turn emits required trace events with one `trace_id`.

Failure conditions: logs are unstructured or lack trace_id.

Required final report format: changed files, tests, validation result, telemetry risks.

## 10. Add LM Studio Responses Provider and CLI vertical slice.

Goal: Add LM Studio Responses-compatible adapter and CLI flow after library verification.

Allowed files: provider adapter, CLI client, adapter tests, CLI tests, library decision docs, as named by a real task spec.

Forbidden files: UI, tools, memory, voice, desktop context, custom SDK without library research.

Required tests/checks: LM Studio payload tests, CLI vertical slice tests, `python scripts/run_all_checks.py`.

Acceptance criteria: CLI sends text, Core calls provider through interface, telemetry logs trace_id, previous_response_id is supported, no provider-specific code enters Core.

Failure conditions: provider logic leaks into Core or the adapter is built without 2026 library verification.

Required final report format: changed files, tests, validation result, dependency risks.
