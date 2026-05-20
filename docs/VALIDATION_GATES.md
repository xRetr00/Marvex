# Validation Gates

Validation gates are mandatory before finishing any task, including a one-line hotfix.

## Voice Worker Runtime Boundary Gate

`scripts/check_voice_worker_runtime_boundaries.py` verifies the dedicated local voice worker process boundary. It requires `packages/voice_worker_runtime`, the worker contract models, no hidden auto-start, no raw audio/transcript persistence defaults, `Hey Marvex` wakeword policy, loopback-only subprocess launch, protected Control Plane worker endpoints, microphone/playback selectors, safe model readiness/checksum reporting, explicit local model downloads, readiness-aware installed-asset backend runtime markers, package-specific Moonshine/SenseVoice/Kokoro/Piper model adapter markers, worker-safe telemetry summaries, Control Plane web worker controls, `sounddevice==0.5.5`, and `docs/VOICE_WORKER_RUNTIME.md` safety wording.

## Required Command

```powershell
uv run python scripts/run_all_checks.py
```

## Future Gate Rework Backlog

Future validation work should move toward structural checks instead of brittle phrase or date latches.

- Prefer machine-readable registries or structural Markdown parsing over exact phrase matching where possible.
- Split `run_all_checks` into explicit profiles such as `fast`, `contract`, `boundary`, `full`, and `dependency`.
- Detect contract changes directly from approval and contract registries so docs, status, and tests stay aligned.
- Enforce dependency-to-adapter ownership so external packages stay behind clean ports and adapters.
- Detect product-surface expansion when a bounded seam starts behaving like an assistant-facing feature.
- Add loopback and no-hidden-autostart exposure gates for any new local worker or service boundary.

For a dependency-changing task, also run the full uv workflow:

```powershell
uv lock
uv sync
uv run python -m pip check
uv run python -m pytest -q
uv run python scripts/run_all_checks.py
```

## Gates

### Docs Accepted Gate

Implementation is blocked while `PROJECT_STATUS.md` has `accepted_docs: false`. The only allowed source files in that state are governance validation scripts under `scripts/`.

### Workspace Policy Gate

Expected folders and required documents must exist.

### Service Placeholder Gate

Every `services/*` folder must remain README-only until its matching service contract is approved in `docs/CONTRACT_APPROVALS.md` and a service-owned entrypoint task exists. Approval alone does not authorize implementation, and any later implementation still needs lifecycle, IPC, health, version, docs, tests, and gates.

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
- RuntimeComposition may mention the approved `lmstudio_responses` provider
  identifier only for the explicit real-provider AssistantRuntime proof path.
- `packages/runtime_composition/local_api_fake_turns_runner.py` may import the
  local API runner/config only as a developer-only fake `/v1/turns` smoke
  composition entrypoint; this exception does not allow RuntimeComposition to
  own HTTP parsing, auth validation, routing, sessions/history, retry/fallback,
  model-selection, or API-key policy.
- `packages/runtime_composition/local_api_lmstudio_responses_runner.py` may
  import the local API runner/config only as a developer-only LM Studio
  Responses `/v1/turns` smoke composition entrypoint with the same restrictions.
- Core and AssistantRuntime must not import or mention the runtime composition
  bridge.
- ProviderRuntime must not import Core or AssistantRuntime.
- CLI may import only the approved runtime composition root functions for the
  existing provider-foundation turn path, the explicit AssistantRuntime
  fake-provider foundation mode, and the explicit LM Studio Responses
  AssistantRuntime proof mode.
- CLI must not import RuntimeComposition internals, ProviderRuntime, concrete
  provider adapters, or provider SDKs.
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

### Local API Boundary Gate

Local API is limited to approved health/version readiness plus the protected
fake-provider `/v1/turns` HTTP/auth/JSON adapter and the protected injected
trace-reader HTTP/auth/JSON adapter.

- `packages/local_api` may import approved contracts, ProcessRuntime, and
  standard-library JSON parsing only.
- `packages/local_api` may use the Python standard-library WSGI runner only for
  manual health/version smoke.
- `packages/local_api` may contain and use the local bearer-token helper for the
  protected `/v1/turns` endpoint.
- `packages/local_api` must default to `127.0.0.1` local host configuration.
- `packages/local_api` must not import Core, AssistantRuntime, ProviderRuntime,
  RuntimeComposition, adapters, telemetry implementation, CLI apps, or services.
- `packages/local_api` must not implement WebSocket, provider request/response
  execution, Core assistant turns, AssistantRuntime provider stage calls,
  RuntimeComposition bridges, sessions/history, routing, retry/fallback,
  model-selection, API-key policy, tools, memory, UI, voice, desktop, vision,
  proactive behavior, or remote binding defaults.
- `/v1/turns` must remain an injected-handler adapter only; no direct
  RuntimeComposition/Core/AssistantRuntime/ProviderRuntime/provider adapter
  execution may be added to the API package.
- Accepted `/v1/turns` execution modes may be injected by explicit manual
  runners; the default local API behavior remains fake-provider only.
- `/v1/traces/{trace_id}` must remain an injected trace-reader adapter only.
  Local API must not own trace storage, telemetry sanitizer policy,
  persistence, streaming, or cross-process lookup.
- `packages/local_api` must not hard-code local token/secret values or print
  token material.
- Service placeholder folders remain README-only until matching contract
  approval and a service-owned entrypoint task exist.
- `scripts/run_all_checks.py` runs the local API boundary gate.

### Local API Client Boundary Gate

Local API client helpers are limited to future Shell/CLI connection proof paths.

- `packages/local_api_client` may read safe local discovery metadata through the
  local service startup discovery reader and use Python standard-library HTTP
  helpers for explicit JSON requests.
- It may call public readiness endpoints without auth and protected turn/trace
  endpoints only when the caller supplies a local bearer token per call.
- It must not store, discover, rotate, print, or cache raw bearer tokens.
- It must not import Local API handlers, Core, AssistantRuntime,
  ProviderRuntime, RuntimeComposition, adapters, telemetry implementation, CLI
  apps, or services.
- It must not implement daemon launch, auto-start, cleanup, supervision,
  WebSocket/events, session/history, retry/fallback, provider routing, model
  selection, persistent telemetry, cross-process traces, tools, memory, UI,
  voice, desktop, vision, or proactive behavior.
- `scripts/run_all_checks.py` runs the local API client boundary gate.

### Telemetry Boundary Gate

Telemetry owns trace event safety, read-time projection, and local persistence.

- `packages/telemetry` may import approved contracts and standard-library file,
  JSON, timestamp, regex, and typing helpers.
- Telemetry persistence must stay telemetry-owned and local-file only unless a
  later task approves another sink.
- Persistent trace stores must sanitize before write and must not persist raw
  prompts, provider payloads, provider outputs, tokens, provider credentials,
  environment values, stack traces with secrets, or full sensitive transcripts
  by default.
- Telemetry must not import Local API, Local API client, local service startup,
  RuntimeComposition, Core, AssistantRuntime, ProviderRuntime, adapters, CLI
  apps, or services.
- Telemetry must not implement sessions/history, memory, tools, UI, voice,
  desktop, vision, proactive behavior, generic provider routing, retry/fallback,
  model selection, daemon supervision, WebSocket/events, or remote trace access.
- `scripts/run_all_checks.py` runs the telemetry boundary gate.

### Local Service Startup Boundary Gate

Local service startup is limited to safe startup metadata and local bearer-token
generation for a future Local API service runner.

- `packages/local_service_startup` may use standard-library startup helpers for
  safe object construction and secure local bearer-token generation.
- It must not import Core, Local API, RuntimeComposition, ProviderRuntime,
  AssistantRuntime, adapters, telemetry, CLI apps, services, or provider SDKs.
- Core, ProviderRuntime, Local API, and RuntimeComposition must not import the
  startup package until a separate service-runner integration task approves it.
- `packages/local_service_startup/local_api_service_runner.py` may import the
  existing Local API runner/config only for the approved startup proof that
  injects a generated local token, prints safe metadata, and optionally writes
  safe discovery metadata through `packages.local_service_startup.discovery`
  when an explicit local-user-scoped path is supplied. This exception does not
  allow Local API handler composition, HTTP parsing ownership, trace storage,
  daemon supervision, routing, retry/fallback, model selection, or broader token
  lifecycle management.
- It must not read environment variables, start daemon or supervisor behavior,
  import server frameworks, implement WebSocket/events, call providers, or own
  routing/retry/fallback/model-selection behavior.
- Public startup metadata must be token-safe; raw local bearer tokens remain
  only in the in-memory startup result for future runner use.
- Future discovery metadata must stay local-user-scoped and safe-only: loopback
  service metadata and token presence are allowed; raw bearer tokens, provider
  credentials, environment values, prompts, traces, sessions/history, remote
  bind addresses, handler config, and provider config are forbidden.
- `scripts/run_all_checks.py` runs the local service startup boundary gate.

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

### Runtime Completion Phase Unlock Gate

Pre-Voice runtime completion must remain implemented and classified by artifact,
not by stale phase-lock wording.

- Grounded-answer runtime must expose citation validation and web evidence to context candidate conversion.
- PromptHarnessRuntime must keep route profiles with non-zero evidence, memory, tool-schema, skill, and approval-policy budgets for relevant routes.
- IntentRuntime must keep multi-step IntentPlan support and clarification stop behavior.
- CapabilityRuntime must keep dynamic tool selection and per-request AutonomyPolicy decisions.
- ProviderSelectionRuntime must keep provider candidate, requirement, retry, fallback, and safe projection models.
- Assistant turn integration must keep provider, tool, web-search, memory, and clarification recovery models.
- LearningRuntime must keep FeedbackEvent ingestion, LearningPipelineRunner, candidate store, audited apply flow, and memory/route/skill candidate outputs.
- ConnectorRuntime must keep policy-controlled sync and auto-fetch runner paths that canonicalize into MemoryTreeRuntime without raw secrets or untracked background sync.
- Control Plane API/web must expose protected feedback/learning, runtime policy, connector, auto-fetch, audit, and diagnostics views without direct frontend mutation.
- MCP launch/install, shell command execution, and file write/delete must be policy-controlled or explicitly not-implemented adapters, not broad governance hard-blocks.
- Stale phase-lock and blanket-block wording for OAuth, auto-fetch, MCP launch, shell execution, retry/fallback, semantic memory, auto-write, and profile write must stay absent from active docs/code; use policy-controlled, not-implemented adapter, or hard-block blacklist-only classifications instead.

`scripts/run_all_checks.py` runs the runtime completion phase unlock gate.

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
  approved/yes with matching structured approval metadata and no conflicting
  status rows.
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
- The gate should consume structured approval rows from
  `docs/CONTRACT_APPROVALS.md` rather than a hardcoded approval date string.
- `scripts/run_all_checks.py` runs the assistant turn contract approval gate.

The gate targets documentation, approval rows, and contract model placement
only. It does not authorize runtime behavior.

### Assistant Runtime Boundary Gate

AssistantRuntime is limited to pure assistant-envelope helpers, no-provider
skeleton behavior, provider-stage helper behavior through injected contracts,
safe one-turn state primitives, and safe assistant stage lifecycle primitives.

- `packages/assistant_runtime` Python source may import approved contracts and
  local assistant-runtime helpers. Existing telemetry event construction imports
  are allowed only for approved provider-stage and structured-output diagnostics.
- `packages/assistant_runtime` Python source must not import or mention Core,
  Local API, local service startup, RuntimeComposition, ProviderRuntime,
  adapters, ports, CLI apps, services, concrete providers, provider bridge terms,
  or future subsystem runtime behavior.
- AssistantRuntime state and lifecycle primitive names must not appear in Core,
  Local API, local service startup, RuntimeComposition, ProviderRuntime, or
  telemetry Python source. Those layers may compose or read approved outputs
  through explicit injected paths only; they must not own assistant state or
  assistant stage lifecycle.
- `packages/assistant_runtime/lifecycle.py` may mention provider response id
  only to expose presence/absence in a safe lifecycle summary. It must not store
  or return provider response id values.
- Strict scans target Python source files only, not README or documentation
  files.
- `scripts/run_all_checks.py` runs the assistant runtime boundary gate.

### SessionRuntime Boundary Gate

SessionRuntime is limited to safe session/conversation references, turn linkage
metadata, current-process projections, and an optional instance-owned registry.

- `packages/session_runtime` may import approved contracts, Pydantic, and
  standard-library collection/typing helpers only.
- SessionRuntime must not import Core, AssistantRuntime, Local API, Local API
  client, local service startup, ProviderRuntime, RuntimeComposition, telemetry,
  adapters, CLI apps, or services.
- Core, AssistantRuntime, Local API, local service startup, ProviderRuntime,
  RuntimeComposition, and telemetry must not import or mention SessionRuntime
  owner models, registries, or projection helpers.
- SessionRuntime must not persist raw prompts, raw provider payloads, raw
  provider outputs, provider response ids, tokens, secrets, credentials,
  environment values, or full transcripts by default.
- SessionRuntime must not implement memory, embeddings/vector search, tools, UI,
  voice, desktop, vision, proactive behavior, generic provider routing,
  retry/fallback, model selection, daemon supervision, WebSocket/events, or
  Local API lifecycle behavior.
- `scripts/run_all_checks.py` runs the session runtime boundary gate.

### MemoryRuntime Boundary Gate

MemoryRuntime is limited to safe memory refs, records, write candidates, policy
decisions, read queries, forget requests, read/forget results, safe projections,
and an optional instance-owned current-process proof store.

- `packages/memory_runtime` may import approved contracts, Pydantic, and
  standard-library collection/date/typing helpers only.
- MemoryRuntime must not import Core, AssistantRuntime, Local API, Local API
  client, local service startup, ProviderRuntime, RuntimeComposition,
  SessionRuntime, telemetry, adapters, CLI apps, services, JSON/file storage,
  SQLite, vector libraries, or provider SDKs.
- Core, AssistantRuntime, Local API, local service startup, ProviderRuntime,
  RuntimeComposition, SessionRuntime, and telemetry must not import or mention
  MemoryRuntime owner models, stores, or projection helpers.
- MemoryRuntime must not implement embeddings, vector search, automatic
  transcript extraction, raw transcript persistence, provider-driven writes,
  tools, UI, voice, desktop, vision, proactive behavior, generic provider
  routing, retry/fallback, model selection, daemon supervision, WebSocket/events,
  or Local API lifecycle behavior.
- `scripts/run_all_checks.py` runs the memory runtime boundary gate.

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

## Capability Platform Foundation Gate

The Capability Platform Foundation gate is enforced by `scripts/check_capability_runtime_boundaries.py` and is part of `scripts/run_all_checks.py`.

The gate requires `packages/capability_runtime` and `packages/adapters/capabilities` to keep clear ownership: CapabilityRuntime owns manifests, eligibility, permission decisions, context delivery, compaction, call proposals, execution requests, result envelopes, safe summaries, approval requirements, loop guards, planning readiness, and verification hooks. Adapters cannot bypass CapabilityRuntime policy and cannot import disabled real backend SDKs directly in this foundation phase.

Protected boundaries:

- Core cannot execute or select tools.
- Local API cannot execute tools.
- RuntimeComposition cannot become a capability registry or brain.
- ProviderRuntime cannot own tools, MCP, skills, or capability policy.
- Telemetry cannot own capability state.
- AssistantRuntime can reference safe capability summary counts but cannot dispatch capabilities or import capability adapters.
- MemoryRuntime and SessionRuntime cannot own tools or capability dispatch.
- local_service_startup cannot own capabilities.

Boundary phrase: adapters cannot bypass CapabilityRuntime policy.

## MCP Adapter Foundation Gate

The MCP Adapter Foundation gate is enforced by `scripts/check_mcp_adapter_boundaries.py` and is part of `scripts/run_all_checks.py`.

The gate permits `packages/adapters/capabilities/mcp.py` to import the official MCP Python SDK for MCP protocol mechanics only. CapabilityRuntime remains authoritative for manifests, permission decisions, call proposals, execution requests, and result envelopes.

The MCP adapter must keep server/tool allowlists, blocked dangerous tool metadata, no arbitrary server launch, no MCP registry install, no automatic calls, and no raw input/output persistence. It must not import transport launch helpers, subprocess/file/browser/socket helpers, Core, AssistantRuntime, ProviderRuntime, RuntimeComposition, Local API, services, or telemetry implementations.

Boundary phrase: CapabilityRuntime remains authoritative.

## Skills Runtime Foundation Gate

The Skills Runtime Foundation gate is enforced by `scripts/check_skills_runtime_boundaries.py` and is part of `scripts/run_all_checks.py`.

Skill is bounded capability context: a locally referenced package of instructions, resources, and optional script metadata that may contribute bounded context only after validation and CapabilityRuntime eligibility/context delivery policy. A skill is not a tool, MCP tool, plugin, connector, integration, prompt engine, script runner, package installer, assistant brain, or provider router.

The gate requires `packages.skills_runtime` to own `SkillRef`, `SkillManifest`, `SkillValidationResult`, `SkillEligibilityDecision`, `SkillPromptContribution`, `SkillResourceRef`, safe skill projections, local-only resource references, policy-override rejection, and test-only deterministic fake skill packages.

CapabilityRuntime remains authoritative for capability refs, manifests, eligibility decisions, context delivery policy, compaction policy, and context packs. SkillsRuntime may project skills into CapabilityRuntime-owned models, but skills cannot override Marvex policy.

Protected boundaries:

- Core cannot own skills or skill selection.
- Local API cannot own skills or expose skill runtime behavior.
- RuntimeComposition cannot become a skill registry or selector.
- ProviderRuntime cannot own skills, prompts, routing, or model selection.
- Telemetry cannot own skill content or raw prompt persistence.
- AssistantRuntime cannot import or dispatch SkillsRuntime.
- MemoryRuntime and SessionRuntime cannot own skill storage or selection.
- local_service_startup cannot install, load, or register skills.
- The MCP adapter cannot own skill manifests or skill prompt contributions.

Blocked: real script execution, arbitrary skill install, remote skill loading, shell/filesystem/browser/desktop/OS access, hidden prompt rewrites, raw prompt/transcript/tool payload persistence by default, and policy/system/developer instruction override.

## Control Plane Foundation Gate

The Control Plane Foundation gate is enforced by `scripts/check_control_plane_boundaries.py` and is part of `scripts/run_all_checks.py`.

Control Plane API must not own policy. It may expose protected local HTTP/auth/JSON endpoints and safe projection models for approvals, providers, capabilities, tools, MCP, skills, telemetry, traces, memory/session refs, agent loops, and settings. Runtime execution projections may show provider proposals, approval states, tool/browser/MCP status, provider continuation status, final response readiness, loop guards, risk level, and safe trace refs, but must not expose raw provider/tool/browser/MCP payloads or execute tools directly. CapabilityRuntime remains authoritative for approvals, permissions, risk classification, execution modes, approved execution requests, dispatch policy, execution state, and loop guards.

Web frontend must never import Python internals. It may talk only to approved local Control Plane / Local API endpoints through typed client helpers and safe JSON contracts.

Protected boundaries:

- Control Plane API cannot import tool adapters directly or execute tools directly.
- Local API and Control Plane API cannot own CapabilityRuntime policy.
- RuntimeComposition cannot become the control plane brain.
- AssistantRuntime remains lifecycle/turn coordination owner, not UI owner.
- Telemetry remains trace/log persistence owner.
- Frontend cannot execute tools directly, import backend Python modules, render secrets, or render raw payloads by default.

Blocked: Orb, desktop overlay, voice UI, vision UI, proactive behavior UI, arbitrary remote access, `0.0.0.0` exposure, direct frontend tool execution, raw secrets/tokens/API keys/environment values, raw transcripts/tool payloads/browser DOM/screenshots, and risky actions outside approval state plus backend policy.
## Agent Execution Loop and Tool-Orchestrated Turn Foundation Gate

The Agent Execution Loop and Tool-Orchestrated Turn Foundation gate is enforced by `scripts/check_agent_execution_loop_boundaries.py` and is part of `scripts/run_all_checks.py`.

CapabilityRuntime remains authoritative for bounded agent-loop state, tool-orchestration state, pending approval state, approved execution requests, denial result envelopes, safe continuation state, loop guards, stop reasons, and telemetry-safe loop summaries. provider tool calls are proposals, not execution permission.

AssistantRuntime may coordinate tool-orchestrated turn lifecycle summaries through `packages.assistant_runtime.tool_orchestration`, but it must not import adapters, construct `CapabilityExecutionRequest`, or execute tools. Tool adapters may execute only approved `CapabilityExecutionRequest` paths and must return safe result envelopes.

Protected boundaries:

- Core cannot execute tools or own agent loops.
- Local API cannot execute tools or own approval decisions directly.
- RuntimeComposition cannot become the agent loop brain.
- AssistantRuntime can coordinate safe summaries but cannot execute adapters.
- ProviderRuntime cannot own tools or loops.
- Telemetry cannot own loop state or persist raw tool/browser/computer/provider payloads by default.
- MemoryRuntime and SessionRuntime can link by safe refs only.
- Adapters cannot bypass CapabilityRuntime permission, approval, execution-request, loop-guard, or result-envelope policy.

Blocked: uncontrolled autonomous agents, shell/terminal execution, filesystem write/edit/delete tools, arbitrary browser/computer actions, credential entry or extraction, purchase/payment/checkout, CAPTCHA or anti-bot bypass, UI, voice, desktop control, vision, proactive behavior, generic provider routing, and raw prompts, transcripts, tokens, tool inputs/outputs, browser DOM, screenshots, provider payloads, or environment values by default. risky actions can pause for human approval.
## Full Tooling and Computer Use Foundation Gate

The Full Tooling and Computer Use Foundation gate is enforced by `scripts/check_full_tooling_boundaries.py` and is part of `scripts/run_all_checks.py`.

CapabilityRuntime remains authoritative for tool and computer-use risk levels, side-effect levels, human approval requirements, approval prompts, approval decisions, execution modes, permission decisions, execution requests, result envelopes, context delivery, compaction, loop guards, and safe telemetry summaries.

The gate permits Playwright only inside the browser adapter boundary. Browser-use is a declared dependency for import-backed and controlled adapter proof, but direct Browser-use SDK execution remains disabled; its adapter may expose safe probes, allowed action categories, exact blocker reasons, approval-required proposals, and denial envelopes only. Latest `browser-use==0.12.6` remains blocked because it pins an older OpenAI SDK than Marvex's OpenAI Agents-compatible stack. OpenAI Computer Use is represented as one adapter backend, not the only Marvex computer-use path. OpenAI Agents SDK tool compatibility, OpenAI function tools, LM Studio tool calls, LiteLLM gateway tools, and MCP tools must become CapabilityRuntime proposals before any future execution. OpenAI Agents SDK cannot own the Marvex agent loop, tool dispatch, policy, prompt harness, or RuntimeComposition.

Protected boundaries:

- Core cannot call Playwright, Browser-use, OpenAI Computer Use, or tools directly.
- Local API cannot execute browser/computer/tool actions directly.
- RuntimeComposition cannot become the browser/computer/tool brain.
- AssistantRuntime cannot execute browser/computer tools.
- ProviderRuntime cannot own tools or tool policy.
- Telemetry cannot persist raw tool/browser/computer payloads by default.
- Adapters cannot bypass CapabilityRuntime permission, approval, execution-mode, context-delivery, loop-guard, or result-envelope policy.

Blocked: shell execution, file write/edit/delete tools, credential access or entry, purchase/payment/checkout, sensitive form submission without future explicit approval flow, CAPTCHA or anti-bot bypass, stealth/proxy scraping, arbitrary desktop OS control, and raw screenshot/DOM/page/tool/provider payload persistence by default.

<!-- file size justification: VALIDATION_GATES.md intentionally stays over 500 lines while active governance gates are centralized for run_all_checks discoverability. -->


## Adaptive Context, Learning, and Governance Gate

The Adaptive Context, Learning, and Governance gate is enforced by `scripts/check_adaptive_context_learning_governance.py` and is part of `scripts/run_all_checks.py`.

This gate protects the pre-Voice adaptive runtime surface:

- grounded routes must have non-zero evidence budget and must inject evidence when evidence exists;
- memory routes must not globally suppress memory blocks;
- tool/browser/MCP routes must expose eligible tool schemas without all-tools dumping;
- citation guidance must only refer to provided evidence refs;
- MCP allowlist changes are reviewable proposals driven by runtime/config/control-plane policy state, not source-only hard-coded mutation;
- read/list/search governance remains allowed while write/delete/send/execute requires approval;
- injection/exfiltration abuse hard-blocks or quarantines with reason codes;
- learning loops can create memory/skill/policy/preference candidates but cannot silently mutate skills or policy.

Semantic memory search uses local deterministic token-vector scoring plus filters for trust, recency, entity, topic, source, source type, hotness, and evidence availability. It does not add a paid/cloud embedding dependency.

Policy state: VoiceRuntime is now a bounded voice I/O foundation only. Orb/Face UI, desktop overlay, and proactive behavior remain not implemented. Tool execution, OAuth sync, auto-fetch, and policy/skill mutation are governed by the autonomy policy layer or review-required candidates; raw sensitive payload persistence remains denied by default.

## Hybrid Intent, Web Search, Grounded Evidence, and Risk Governance Gate

The Hybrid Intent, Web Search, Grounded Evidence, and Risk Governance gate is enforced by `scripts/check_hybrid_intent_web_search_governance.py` and is part of `scripts/run_all_checks.py`.

This gate requires real runtime dependencies and paths for `semantic-router`, `llama-index-core`, DDGS, SearXNG adapter support, web search models, grounded citation validation, and risk-based governance. It proves required intent examples route through `hybrid_intent_runtime`, not keyword-only deterministic fallback.

The gate protects these invariants:

- Semantic Router and LlamaIndex are route/selector components only; IntentRuntime owns policy and route decisions.
- SearXNG and DDGS are web search adapters only; they do not own browser actions, account access, downloads, or policy.
- Read/list/search/inspect/summarize and safe public web search are not hard-blocked by default.
- Write/delete/send/upload/install/run/connect/private-account actions require approval.
- Malware, credential theft, prompt-injection exploitation, command-injection exploitation, exfiltration, unauthorized account abuse, CAPTCHA or anti-bot bypass, stealth abuse, destructive action without consent, payment/checkout without explicit approval, and policy override attempts hard-block or quarantine.
- Grounded answer citations must map to provided evidence refs.
- PromptHarnessRuntime may receive bounded evidence sections only; no all-tools, all-memory, raw transcript, raw provider payload, raw browser DOM, or raw screenshot dumping.

Policy state: VoiceRuntime is now a bounded voice I/O foundation only. Orb/Face UI, desktop overlay, and proactive behavior remain not implemented. Tool execution, MCP install/execute, OAuth sync, and auto-fetch are governed by autonomy policy and approval state; raw payload persistence remains denied by default.

## Intent, Context, and Prompt Harness Foundation Gate

The Intent, Context, and Prompt Harness Foundation gate is enforced by `scripts/check_intent_context_prompt_boundaries.py` and is part of `scripts/run_all_checks.py`.

IntentRuntime exists as the owner for intent refs, candidates, classification requests/results, confidence buckets, route decisions, risk signals, ambiguity signals, clarification decisions, and safe intent projections. ContextRuntime/PromptHarness owns bounded context packs, context delivery policy, prompt sections, prompt harness plans, compaction/offload decisions, planning readiness, validation results, and safe telemetry summaries.

CapabilityRuntime remains authoritative for capability policy, permissions, eligibility, dispatch, approvals, execution requests, result envelopes, and loop guards. The harness may select eligible schema projections by intent/context, but it cannot approve execution or bypass policy.

Protected boundaries:

- Core does not own intent routing or prompt harness assembly.
- Local API does not assemble prompts.
- RuntimeComposition does not become the intent/context brain.
- ProviderRuntime does not own context delivery or generic model routing.
- Telemetry records safe summaries only and does not own prompt/context models.
- MemoryRuntime does not assemble prompts.
- AssistantRuntime may consume safe harness plans in future work but must not dump raw prompts.
- Adapters cannot own policy, automatic retry loops, autonomous planning loops, or raw prompt access.
- Semantic Router may build adapter-local route definitions and scores, but it cannot own IntentRuntime policy or dispatch.
- Guardrails may validate safe projections only when a compatible package exists; it cannot assemble prompts, see raw prompt payloads, or run automatic retry loops.
- LlamaIndex and LangChain/LangGraph remain deferred and cannot own Core, MemoryRuntime, RuntimeComposition, planning loops, context injection, or prompt harness behavior.

Blocked: raw prompt/transcript/provider/tool/browser payload persistence by default, all-tools dumping, all-skills dumping, all-memory dumping, embeddings/vector search without a separate decision, autonomous planners, recursive loops, browser/computer actions, UI, voice, desktop, vision, proactive behavior, and generic provider routing.

Boundary invariant: no all-tools dumping, no all-memory dumping, and no raw prompt persistence by default.

## End-to-End Assistant Turn Integration Foundation Gate

The End-to-End Assistant Turn Integration Foundation gate is enforced by `scripts/check_end_to_end_turn_boundaries.py` and is part of `scripts/run_all_checks.py`.

The integration spine may compose approved runtime layers in `packages.assistant_turn_integration`, but it must not become a generic provider router, model selector, autonomous planner, shell/filesystem/browser executor, raw prompt store, or replacement policy engine.

Protected ownership:

- Local API owns HTTP/auth/JSON only and receives the turn handler by injection.
- CapabilityRuntime owns policy/approval/dispatch, execution requests, result envelopes, and loop guards.
- IntentRuntime owns intent/route decisions.
- ContextRuntime owns context selection.
- PromptHarnessRuntime owns prompt plan construction.
- AssistantRuntime owns lifecycle coordination and provider-stage helpers.
- Telemetry owns trace persistence and safe trace projections.
- Control Plane owns safe visibility and approval API only.
- RuntimeComposition does not become the end-to-end assistant brain.

Blocked: raw prompt/transcript/tool/provider/browser payload persistence by default, direct frontend or Local API tool execution, arbitrary browser/computer actions, shell execution, filesystem write/edit/delete, generic provider routing/model selection, Orb, desktop overlay, vision, proactive behavior, and any voice behavior outside the bounded VoiceRuntime foundation.

### Assistant Intelligence and Tool-Using Runtime Boundary Gate

`check_assistant_intelligence_tool_runtime_boundaries.py` enforces the Assistant Intelligence and Tool-Using Runtime Integration boundary. It checks that the integration spine uses route-specific intent/context/prompt selection, allowlisted MCP live proof through the MCP adapter, approval resume/deny/cancel state, safe browser workflow metadata, provider continuation input summaries, malformed provider argument rejection, and provider tool-call proposal mapping, SQLite memory safe-ref participation, Memory Tree evidence refs, semantic-router-backed intent classifier injection, and trace-searchable safe runtime status without letting provider tool calls become execution permission or raw provider payload persistence.

Provider tool calls remain proposals. Browser and MCP adapters own SDK mechanics only after CapabilityRuntime approval. Memory participation is by MemoryRuntime safe refs/previews and Memory Tree evidence refs/counts only, and trace search stays Telemetry-owned safe summary search. Core, Local API, RuntimeComposition, AssistantRuntime, ProviderRuntime, and Telemetry must not import browser/MCP/provider tool-call adapter owners directly or persist raw tool/browser/MCP/provider payloads by default.

## Marketplace, Memory Backend, and Control Plane Expansion Gate

The Marketplace, Memory Backend, and Control Plane Expansion gate is enforced by `scripts/check_marketplace_memory_control_plane_boundaries.py` and is part of `scripts/run_all_checks.py`.

MarketplaceRuntime owns read-only MCP registry metadata, Skill marketplace metadata, manifest validation, allowlist proposal state, and safe enable/disable projections. MemoryRuntime owns the local SQLite memory backend adapter and safe inspect/forget projections. Control Plane API owns HTTP/auth/JSON routes only and must not become policy owner or tool executor.

Protected boundaries:

- MCP marketplace browsing is read-only metadata; no arbitrary install, server launch, or auto execution.
- Skill marketplace entries are approved/local metadata only; no untrusted script execution or remote loading.
- Memory backend storage is local SQLite behind MemoryRuntime and rejects raw transcript/secret-like content by default.
- Trace search returns Telemetry-owned safe summaries only.
- Control Plane API and frontend cannot execute tools directly or render raw secrets/payloads.
- CapabilityRuntime remains authoritative for policy, approval, risk, and dispatch.

Policy state: MCP install/execute, skill update/create, and shell execution are governed by the autonomy policy layer and approval state. Arbitrary skill remote execution, credential storage, raw prompt/transcript/tool/provider/browser payload rendering or persistence by default, remote exposure, Orb, desktop overlay, proactive behavior, and voice behavior outside the bounded VoiceRuntime foundation remain not implemented or denied.

### Governance Classification Gate

Every major implemented or future surface must be classified in `docs/GOVERNANCE_CLASSIFICATION.md` as one of: documented surface, bounded foundation, evaluation seam, draft service contract, policy-controlled surface, safety-restricted surface, or future product surface.

This gate enforces the rule that existing code is not approval. Future work is allowed only when supported by the current goal spec, `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and relevant architecture docs.

The gate requires classification for provider foundation, assistant turn contracts, assistant turn integration, telemetry, Local API, Control Plane API, Control Plane web, CapabilityRuntime, tool execution foundations, MCP adapter/seam, browser/computer-use adapter/seam, MemoryRuntime, MarketplaceRuntime, SessionRuntime, intent/prompt harness seams, service placeholders, future voice, future desktop agent, future shell/orb UI, future proactive behavior, and future vision.

### God-File And Assistant-Brain Risk Gate

Known risk files have stricter size limits than the default 500-line rule. `packages/capability_runtime/execution.py` must remain a re-export facade after the cleanup split. `packages/assistant_turn_integration/spine.py` must remain composition glue, not a central assistant brain.

## OpenHuman-Style Memory Tree and Connectors Foundation Gate

The OpenHuman-Style Memory Tree and Connectors Foundation gate is enforced by `scripts/check_memory_tree_connector_boundaries.py` and is part of `scripts/run_all_checks.py`.

MemoryTreeRuntime owns canonicalization, chunks, scoring, SQLite tree index, source/topic/global/daily trees, evidence links, traversal, and vault projection. ConnectorRuntime owns connector manifests, OAuth metadata, permission decisions, sync request/result envelopes, and auto-fetch policies. Control Plane API and web display safe projections and policy toggles only.

Protected boundaries:

- Memory tree summary nodes require provenance evidence.
- Auto-fetch exists as a configurable policy surface and remains disabled by default unless explicitly enabled by policy.
- Connector manifests are read-only ingestion foundations; broad account actions are not implemented.
- OAuth tokens and credentials are not exposed through safe projections, telemetry, or Control Plane.
- Control Plane forget/delete and auto-fetch endpoints do not directly start deletion, sync, or account actions.
- Authlib is isolated behind a connector adapter import proof and cannot own ConnectorRuntime policy.
- Airbyte, Nango, Meltano/Singer, and Pipedream remain reference/deferred seams until a future backend-specific goal adopts one safely.

Blocked: copied OpenHuman code, paid/cloud-only required connector services, hidden sync, raw token persistence in public metadata, raw email/doc/message body telemetry, raw transcripts/provider/tool payload persistence by default, broad account actions such as sending email or posting Slack messages, remote exposure, voice, desktop, vision, and proactive behavior.

## Autonomy Modes and Runtime Policy Control Plane Gate

The Autonomy Modes gate is enforced by `scripts/check_autonomy_policy_boundaries.py` and is part of `scripts/run_all_checks.py`.

Marvex runtime policy is mode controlled through `AutonomyPolicy` and Control Plane safe projections. `locked_down`, `ask_before_risky`, `auto_marvex`, and `custom` modes expose a capability permission matrix. Safe read/list/search, public web search, public page read/extract, MCP listing, memory search, and semantic memory search cannot be globally hard-blocked. Normal assistant capabilities such as MCP execute, skills use/update/create, connector OAuth/live sync, auto-fetch, memory/profile writes, browser/computer actions, file write/delete, external send/upload, retry/fallback, and learning mutation candidates must be policy-controlled as allow/ask/deny/quarantine decisions or clearly not implemented.

Hard-block is reserved for blacklist abuse categories only: malware, credential theft/extraction, data exfiltration, prompt-injection exploitation, command-injection exploitation, CAPTCHA/anti-bot bypass, stealth abuse, unauthorized account access, illegal destructive abuse, and payment/checkout without explicit enabled policy and approval path. Every deny, quarantine, or hard-block decision must include reason codes and a safe audit projection. Control Plane can update policy mode and display audit records, but it must not execute tools directly or render raw secrets/payloads.

## Voice Runtime Foundation Gate

The Voice Runtime Foundation gate is enforced by `scripts/check_voice_runtime_boundaries.py` and is part of `scripts/run_all_checks.py`.

VoiceRuntime owns voice I/O orchestration only: wakeword, VAD, audio buffering, chunk aggregation, STT/TTS backend selection, model/voice registries, sentence clamping, queued speech, early speech, barge-in state, voice personality settings, safe voice turn envelopes, and Control Plane safe projections.

Protected boundaries:

- VoiceRuntime must not own intent routing, tools, memory, provider routing, capability policy, autonomy policy, visual UI, desktop overlay, Orb/Face UI, or proactive non-voice behavior.
- STT/TTS/wakeword/VAD adapters must not call assistant internals directly.
- Voice turns must use injected assistant-turn and policy decision callbacks and cannot bypass AutonomyPolicy or CapabilityRuntime approval semantics.
- Wakeword 24/7 mode must be explicit, visible, policy-controlled, and disabled by default.
- Raw audio, generated audio, raw transcripts, raw provider/tool payloads, secrets, and backend internals must not be persisted or rendered by default.
- Early speech cannot claim facts without evidence, and barge-in must interrupt playback/queued speech state.
- STT, TTS, wakeword, VAD, voice/model downloads, voice tests, backend selectors, voice personality, audio retention, and telemetry summaries must be visible through protected Control Plane APIs/web views only.

Adopted backend dependencies: Moonshine v2 through `moonshine-voice`, SenseVoice-Small through `funasr`, `sherpa-onnx` plus `sherpa-onnx-core`, `kokoro-onnx`, `piper-tts`, `stream2sentence`, `silero-vad`, and `webrtcvad-wheels`. Actual model/voice downloads remain explicit user-triggered operations into safe local model directories.

Blocked: hidden recording, raw audio/transcript persistence by default, frontend engine execution, direct Local API tool/provider execution, VoiceRuntime-owned service daemon behavior, Orb/Face UI, desktop overlay, vision, and proactive non-voice behavior.

## Voice Worker Runtime Boundary Gate

The Voice Worker Runtime Boundary gate is enforced by `scripts/check_voice_worker_runtime_boundaries.py` and is part of `scripts/run_all_checks.py`.

VoiceWorkerRuntime owns the local worker process boundary, explicit lifecycle commands, heartbeat/status, local microphone and playback adapters, model asset readiness, wakeword test readiness, worker-safe telemetry summaries, and protected Control Plane projections.

Protected boundaries:

- VoiceWorkerRuntime must remain local-only and must reject non-loopback process bindings.
- VoiceWorkerRuntime must not own assistant policy, AutonomyPolicy, CapabilityRuntime, intent routing, tools, memory, provider routing, RuntimeComposition supervision, Local API internals, Orb/Face UI, desktop overlay, vision, or proactive non-voice behavior.
- Worker start, stop, pause, resume, device config reload, mic test, playback test, wakeword test, STT/TTS tests, model install/remove, backend switching, and active voice switching must be user-visible protected Control Plane or explicit process commands; no hidden auto-start is allowed.
- Microphone capture and playback must stay behind local audio adapters. Physical device validation may be manual, but runtime paths and mocked tests must exist.
- Raw audio, generated audio, raw transcripts, backend internals, secrets, provider payloads, and tool payloads must not be persisted or rendered by default.
- Model and voice installs/downloads must be explicit user-triggered operations under the safe local voice asset root. Missing model files must report `not_installed`; checksum mismatches must report `blocked`; wakeword tests must report not-ready until the Hey Marvex sherpa-onnx KWS asset is installed and wakeword is enabled.
- Worker telemetry must persist/project safe summaries only: lifecycle/device/capture/wakeword/VAD/STT/TTS/playback/barge-in/error counts and durations, never raw audio or transcripts.
- Barge-in must cancel playback state and queued TTS state. Early speech must remain bounded, rate-limited, and unable to claim facts without evidence.

Adopted worker dependency: `sounddevice==0.5.5`, isolated behind `SoundDeviceAudioAdapter`. CI uses `FakeLocalAudioAdapter` for deterministic device/capture/playback tests because physical microphone and speaker hardware are host-local.

Blocked: hidden recording, raw audio/transcript/generated-audio persistence by default, hidden downloads, arbitrary path writes, remote worker exposure, always-running 24/7 wakeword supervision without explicit visible control, real model downloads in automated validation, Orb/Face UI, desktop overlay, vision, and proactive non-voice behavior. Approved VoiceWorker work may implement explicit user-triggered local model downloads and local-only persistent worker supervision behind the worker contract.
