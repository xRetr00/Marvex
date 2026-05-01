# AI Agent Rules

This project will be built by AI coding agents. The user is not expected to verify code correctness manually.

## Required Before Work

Every task starts with a task spec.

Every task must follow `docs/GIT_RULES.md`. Normal small and medium tasks run
directly on `main`; agents must not create branches automatically.

The agent must identify:

- goal
- allowed files
- forbidden files
- Context Pack
- Assistant Turn Spine fit for assistant-level work
- Assistant Turn Contract Map input/output ownership and approval status
- Assistant Turn Envelope distinction for future assistant contract work
- Runtime Ownership fit for runtime-related work
- Library Research Matrix fit for custom infrastructure or dependency work
- contract impact
- ownership boundary
- tests required
- validation commands required
- rollback plan

## Context Budget Rules

Agents must obey `docs/AGENT_CONTEXT_RULES.md`.

Before source reads, agents must use the task spec Context Pack and the
orientation docs:

- `docs/SYSTEM_MAP.md`
- `docs/MODULE_INDEX.md`

Agents must not perform broad repo discovery unless the task explicitly allows a
repo-wide audit or the user approves widening scope.

Agents must not run broad `rg`, repo-wide `rg --files`, or whole-file reads of
large files by default. They must start with targeted searches inside the
allowed task scope.

Agents must stop and ask before expanding read scope outside the Context Pack,
allowed files, or approved task boundary.

## Implementation Rules

- One slice only.
- Follow `docs/GIT_RULES.md` for plan, approval, implementation, validation, commit, and push flow.
- Do not create a branch unless the user explicitly approves it first.
- Do not start the next task while the current task has uncommitted changes.
- No "fix all bugs" prompts.
- No unrelated edits.
- No architecture changes during bug fixes.
- No implementation before docs are accepted.
- No feature before contract.
- The provider turn is not the assistant turn.
- Assistant-level work must answer the Assistant Turn Spine gate before
  implementation.
- Assistant-level work must name input/output contracts and approval status from
  the Assistant Turn Contract Map before implementation.
- Assistant contract work must distinguish provider-foundation contracts from
  assistant-envelope contracts and must not repurpose `TurnInput`, `TurnOutput`,
  or `FinalResponse` as assistant-turn contracts.
- Runtime-related work must identify the owning runtime and pass the Runtime
  Ownership gate before implementation.
- Work proposing custom infrastructure or new dependencies must name the relevant
  library research or decision record from `docs/LIBRARY_RESEARCH_MATRIX.md`.
- No implementation task without a real task spec file.
- No task id as a substitute for a task spec.
- No broad repository discovery without Context Pack approval.
- No provider logic in Core.
- No UI logic in Core.
- No tool execution in UI.
- No giant orchestrator.
- Ports are minimal contracts only, not managers, registries, routers, factories, or implementation containers.
- `ProviderPort` may define only the provider interface contract.
- Port files must not mention LiteLLM, LM Studio, OpenAI, OpenRouter, Anthropic, Gemini, or other concrete provider names.
- Port files must not contain provider selection, retry policy, API key handling, config loading, streaming logic, tool logic, history logic, or parsing logic.
- Tool ports stay minimal; `ToolExecutorPort` is contract-only with `execute(ToolCall) -> ToolResult`.
- Built-in tools live under `packages/adapters/tools/<tool_family>/<tool_name>.py`.
- Tool selection, permission, and dispatch belong to `tool_runtime/`, not ports.
- Any adapter importing Core is forbidden.
- Any Core file importing adapters is forbidden.

## Anti-God-Object Task Checks

Every implementation task spec must answer:

- What is the single ownership boundary?
- What standalone module owns the work?
- Why does the work not belong in central orchestration?
- How does the design avoid creating a new god object?
- What is the file size risk?
- What dependency direction is allowed?

If a task introduces or changes a port, the task spec must also answer:

- What is the minimal method surface?
- What implementation names are forbidden?
- What runtime owns selection and dispatch?
- How will we prevent this port from becoming a god file?

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
- commit hash or explicit no-commit reason
- push status
- current Git status summary
- risks
- deferred work

## Stop Conditions

The agent must stop and report instead of coding if:

- the task has no approved contract
- the task mentions assistant-level intent, tools, memory, voice, desktop, UI,
  proactive behavior, service runtime, HTTP/IPC, or telemetry persistence without
  answering the Assistant Turn Spine gate
- the task has no real task spec file
- the task requires a forbidden v1 module
- the task would create a god object
- the task requires custom SDK code while a maintained SDK may exist
- the task proposes custom infrastructure or a new dependency without answering
  the Library Research Matrix gate
- the task edits unrelated files
- the current task has uncommitted changes and the agent is asked to start another task
- branch creation would be needed but the user has not approved creating a branch
