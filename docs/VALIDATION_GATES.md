# Validation Gates

Validation gates are mandatory before finishing any task, including a one-line hotfix.

## Required Command

```powershell
python scripts/run_all_checks.py
```

## Gates

### Docs Accepted Gate

Implementation is blocked while `PROJECT_STATUS.md` has `accepted_docs: false`. The only allowed source files in that state are governance validation scripts under `scripts/`.

### Workspace Policy Gate

Expected folders and required documents must exist.

### Service Placeholder Gate

Every `services/*` folder must remain README-only until its service contract is approved in `docs/CONTRACT_APPROVALS.md` and `implementation_allowed` is `yes`.

### Forbidden Modules Gate

V1-forbidden modules must not appear as implementation directories.

### File Size Gate

No non-doc file may exceed 500 lines without explicit justification.

### Port Boundary Gate

Port files are interface contracts only.

- Port contract files over 120 lines fail unless explicitly justified.
- Port contract files mentioning concrete implementation names fail.
- Adapter files importing Core fail.
- Core files importing adapters fail.
- Registry and factory files over 250 lines require split or explicit justification.

### ProviderRuntime Boundary Gate

ProviderRuntime is the only boundary allowed to import approved concrete provider adapters.

- Core must not import ProviderRuntime or adapters.
- CLI must not import concrete provider adapters.
- ProviderPort must not mention concrete provider names.
- ProviderRuntime may import only approved provider adapters.
- ProviderRuntime must not contain routing, fallback, retry, session, history, plugin, daemon, server, health routing, or model routing logic.
- Strict runtime scans target Python source files only, not README files.

### ProcessRuntime Boundary Gate

ProcessRuntime is limited to local HealthCheck and VersionInfo object
construction until an explicit future integration task.

- ProcessRuntime may import contracts and approved standard-library modules only.
- ProcessRuntime must not import Core, adapters, ProviderRuntime, telemetry, apps, or services.
- ProcessRuntime Python source must not contain HTTP, server, daemon, subprocess, supervisor, thread, socket, requests, httpx, urllib, filesystem, environment, CLI, provider runtime, tool, memory, intent, voice, or desktop behavior tokens.
- Core and ProviderRuntime must not import or mention `packages.process_runtime`.
- CLI may import or mention `packages.process_runtime` only from
  `apps/cli/main.py` for approved local health/version commands.
- `packages/process_runtime/process_runtime.py` over 250 lines requires the explicit phrase `process runtime size justification`.
- Strict runtime scans target Python source files only, not README or documentation files.

### Vaxil Boundary Gate

Vaxil may be mentioned only as a cautionary research source. Code reuse language and imports are forbidden.

### Library Decision Gate

Dependency recommendations must include official source, maintenance status, why use it, why not custom code, and fallback if abandoned.

Runtime dependencies listed in `[project].dependencies` must have matching
decision records under `docs/library-decisions/` with `pyproject dependency`
and `declared dependency` fields.

### Schema Version Gate

Active Provider Foundation docs, examples, tests, and approval rows must use the
schema version defined in `docs/SCHEMA_VERSION_POLICY.md`.

Deprecated schema versions may be mentioned only as historical notes in the
schema-version policy and in validation code that rejects deprecated active
references.

### Project Status Gate

`PROJECT_STATUS.md` must reflect completed milestones and must not point to
stale next tasks after a governance cleanup has completed.

### Agent Context Budget Gate

The agent context architecture docs must remain present and discoverable.

- `docs/SYSTEM_MAP.md`, `docs/MODULE_INDEX.md`, and `docs/AGENT_CONTEXT_RULES.md` must exist.
- `docs/AI_AGENT_RULES.md` must point agents to `docs/AGENT_CONTEXT_RULES.md`.
- `docs/TASK_PLAN.md` must mention the Context Pack requirement.
- `templates/TASK_SPEC.md` must retain the mandatory `context_pack` fields.
- `docs/AGENT_CONTEXT_RULES.md` must retain the core read-budget rules for no default full-repo scan, no broad `rg`, no repo-wide `rg --files` unless approved, justified large-file reads, and approval before widening scope.
- This gate uses targeted phrase and field checks only. It does not inspect shell history or enforce actual agent tool usage.

### Assistant Turn Spine Gate

The provider turn is not the assistant turn. The current provider path is only a
foundation/test path.

This gate requires:

- `docs/ASSISTANT_TURN_SPINE.md` exists.
- `docs/ASSISTANT_TURN_SPINE.md` states that the provider turn is not the
  assistant turn.
- `docs/AI_AGENT_RULES.md` references the Assistant Turn Spine.
- `templates/TASK_SPEC.md` includes Assistant Turn Spine gate questions.
- Future implementation task specs that mention assistant-level tools, memory,
  voice, desktop, proactive behavior, UI, HTTP/IPC, service runtime, or telemetry
  persistence must also mention Assistant Turn Spine and contract approval.

The gate is intentionally conservative. It targets task specs, templates, and
governance docs, not historical reports.

### Assistant Turn Contract Map Gate

Current approved contracts are provider-foundation contracts, not assistant-turn contracts.

This gate requires:

- `docs/ASSISTANT_TURN_CONTRACT_MAP.md` exists.
- The contract map states that provider-foundation contracts must not be silently
  repurposed as assistant-turn contracts.
- The contract map lists required assistant-level contract families before
  implementation.
- `templates/TASK_SPEC.md` requires assistant-level implementation tasks to name
  input/output contracts and approval status.
- `scripts/run_all_checks.py` runs the contract map gate.

The gate targets governance docs and task templates only. It does not approve
contracts and does not inspect runtime behavior.

### Runtime Ownership Gate

Core owns the assistant lifecycle envelope. AssistantTurnRuntime owns assistant
stage dispatch. Subsystem runtimes own domain selection, dispatch, lifecycle, and
execution.

This gate requires:

- `docs/RUNTIME_OWNERSHIP.md` exists.
- `docs/RUNTIME_OWNERSHIP.md` states that Core owns lifecycle envelope, not
  assistant stage internals.
- `docs/RUNTIME_OWNERSHIP.md` states that AssistantTurnRuntime owns stage
  dispatch, not subsystem internals.
- `docs/RUNTIME_OWNERSHIP.md` states ProviderRuntime and ContextBuilder
  forbidden responsibilities.
- `templates/TASK_SPEC.md` requires runtime-related tasks to identify runtime
  ownership.
- `scripts/run_all_checks.py` runs the runtime ownership gate.

The gate targets governance docs and task templates only. It does not implement
runtime behavior.

### Task Spec Gate

Every implementation task requires a real task spec file. A task id alone is not sufficient.

The task spec must define goal, allowed files, forbidden files, contract impact, ownership boundary, tests required, validation commands, rollback plan, and final report format.

### Contract Approval Gate

Implementation may use only contracts listed in `docs/CONTRACT_APPROVALS.md` with approval status `approved` and `implementation_allowed` set to `yes`.
