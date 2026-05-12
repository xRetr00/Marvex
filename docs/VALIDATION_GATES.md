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

### Runtime Composition Boundary Gate

RuntimeComposition owns narrow bridge/factory composition only.

- `packages/runtime_composition` may import approved contracts, telemetry sink
  contracts, ProviderRuntime factory/config, and the Core
  assistant-provider-stage helper.
- `packages/runtime_composition` must not import concrete provider adapters,
  AssistantRuntime directly, provider ports, CLI apps, or services.
- `packages/runtime_composition` must not contain provider routing,
  retry/fallback policy, session/history behavior, API-key policy, model
  selection, tool runtime, or memory runtime behavior.
- Core and AssistantRuntime must not import or mention the runtime composition
  bridge.
- ProviderRuntime must not import Core or AssistantRuntime.
- CLI must not import the runtime composition bridge until a separate explicit
  opt-in task approves a caller.
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

### Assistant Turn Envelope Gate

The smallest assistant-level envelope is `InputEvent`, `AssistantTurnInput`,
`AssistantTurnResult`, and `AssistantFinalResponse`.

This gate requires:

- `docs/ASSISTANT_TURN_ENVELOPE.md` exists.
- `docs/ASSISTANT_TURN_ENVELOPE.md` states that `TurnInput, TurnOutput, and FinalResponse must not be silently repurposed` as assistant-turn contracts.
- `docs/ASSISTANT_TURN_ENVELOPE.md` states provider contracts remain
  provider-foundation scoped.
- `docs/ASSISTANT_TURN_ENVELOPE.md` states assistant-level contracts must wrap
  or reference provider-foundation contracts, not mutate them into assistant
  contracts.
- `docs/ASSISTANT_TURN_ENVELOPE.md` includes anti-escape-hatch rules for
  `TurnInput.metadata`, `ProviderRequest.provider_options`,
  `ProviderResponse.raw_metadata`, CLI args, and `TraceEvent.data`.
- `templates/TASK_SPEC.md` requires future assistant contract tasks to identify
  whether work touches provider-foundation contracts or assistant-envelope
  contracts.
- `scripts/run_all_checks.py` runs the assistant turn envelope gate.

The gate targets governance docs and task templates only. It does not implement
contracts, approve contracts, or inspect runtime behavior.

### Assistant Turn Contract Approval Gate

Approved assistant-envelope contracts must remain governed separately from
runtime behavior after the explicit model implementation task creates contract
models.

This gate requires:

- `docs/ASSISTANT_TURN_CONTRACTS.md` documents `InputEvent`,
  `AssistantTurnInput`, `AssistantTurnResult`, and `AssistantFinalResponse`.
- Each approved contract lists required fields and a small JSON example.
- `docs/CONTRACT_APPROVALS.md` lists the four assistant-envelope contracts as
  approved/yes with approver `user` and approval date `2026-05-01`.
- Contract docs include closed assistant-envelope enum values, exact
  `payload`/`payload_ref` carrier rules, seed-only `policy_context`, minimal
  stage summary shape, provider-reference constraints, and candidate-only memory
  write wording.
- Contract docs include concrete reference formats for payload, session, identity,
  provider turn, tool result, memory result, output event, and session result
  references.
- Contract docs include minimal nested shapes for `privacy` and `policy_context`
  and closed status values for stage/provider summaries.
- Contract docs require `privacy` and `policy_context` minimal keys, and provider
  turn refs must use the typed `ref_type` / `ref_id` reference strategy.
- The gate parses fenced JSON examples in `docs/ASSISTANT_TURN_CONTRACTS.md`
  and fails on invalid JSON.
- The gate checks that `packages/contracts/models.py` defines the four
  assistant envelope contract classes.
- The gate checks that no app, service, runtime, or test helper defines
  duplicate assistant envelope contract classes.
- Approval is limited to these four assistant envelope contracts and does not
  authorize runtime behavior.
- Provider-foundation contracts are not silently reclassified as assistant
  contracts.
- `scripts/run_all_checks.py` runs the assistant turn contract approval gate.

The gate targets documentation, approval rows, and contract model placement
only. It does not authorize runtime behavior.

### Assistant Runtime Boundary Gate

AssistantRuntime is limited to pure assistant-envelope helper and no-provider
skeleton behavior until a separate task approves runtime integration.

- `packages/assistant_runtime` Python source may import approved contracts and
  local assistant-runtime helpers.
- `packages/assistant_runtime` Python source must not import or mention Core,
  ProviderRuntime, adapters, ports, CLI apps, services, concrete providers,
  provider bridge terms, or future subsystem runtime behavior.
- Strict scans target Python source files only, not README or documentation
  files.
- `scripts/run_all_checks.py` runs the assistant runtime boundary gate.

### Provider Structured Output Boundary Gate

Provider structured output is limited to no-network validation of already
available structured payloads into approved Marvex-owned Pydantic contracts.

- `packages/provider_structured_output` Python source may import
  `packages.contracts`, Pydantic, and standard-library modules only.
- `packages/provider_structured_output` Python source must not import Core,
  AssistantRuntime, ProviderRuntime, adapters, ports, CLI apps, or services.
- `packages/provider_structured_output` Python source must not mention concrete
  providers, prompt rendering, provider response ids, or deferred structured
  output frameworks.
- `scripts/run_all_checks.py` runs the provider structured output boundary gate.

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

### Library Research Matrix Gate

Future subsystem implementation requires a library decision record before custom
code or new dependency.

This gate requires:

- `docs/LIBRARY_RESEARCH_MATRIX.md` exists.
- `docs/LIBRARY_RESEARCH_MATRIX.md` states the current approved
  provider-foundation posture: LiteLLM, OpenAI SDK, and Pydantic.
- `docs/LIBRARY_RESEARCH_MATRIX.md` states that Task 045A expanded discovery
  beyond the first shortlist.
- `docs/LIBRARY_RESEARCH_MATRIX.md` references broad ecosystem discovery
  sources such as `awesome-python`, `best-of-python`, `awesome-llm-apps`, an
  awesome agent-framework list, and an MCP ecosystem/source list.
- `docs/LIBRARY_RESEARCH_MATRIX.md` states that no framework or library may own
  Core or AssistantTurnRuntime.
- `docs/LIBRARY_RESEARCH_MATRIX.md` states libraries must stay behind
  ports/adapters/runtimes.
- `templates/TASK_SPEC.md` requires tasks proposing custom infrastructure or new
  dependencies to name the library research or decision record.
- `scripts/run_all_checks.py` runs the library research matrix gate.

The gate targets governance docs and task templates only. It does not approve
libraries, add dependencies, or inspect product runtime behavior.

### Task Spec Gate

Every implementation task requires a real task spec file. A task id alone is not sufficient.

The task spec must define goal, allowed files, forbidden files, contract impact, ownership boundary, tests required, validation commands, rollback plan, and final report format.

### Contract Approval Gate

Implementation may use only contracts listed in `docs/CONTRACT_APPROVALS.md` with approval status `approved` and `implementation_allowed` set to `yes`.
