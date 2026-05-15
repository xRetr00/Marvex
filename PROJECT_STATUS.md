# Project Status

current_phase: real_provider_local_api_turns_decision_pack

implementation_status: real_provider_local_api_turns_decision_recorded

accepted_docs: true

current_governance_gate:

Task 130 Real-Provider Local API Turns Decision Pack

## Validation Baseline

Latest full validation baseline from Task 130:

- `python scripts\run_all_checks.py` -> PASS all validation checks passed
- `python -m pytest -q` -> 691 passed, 1 skipped

Recent local API/runtime milestones:

- RuntimeComposition owns explicit fake and LM Studio Responses
  AssistantRuntime bridge proofs; CLI uses only explicit proof flags for those
  paths and default CLI behavior remains provider-foundation scoped.
- Local API now has public loopback `/health` and `/version`, protected fake
  `/v1/turns`, and protected injected `GET /v1/traces/{trace_id}`. Local API
  owns HTTP/auth/JSON only and receives execution/trace behavior by injection.
- The developer-only fake `/v1/turns` runner shares one current-process
  `InMemoryTraceReader` instance between fake turn recording and protected trace
  reads. Task 129 smoke verified five safe projected events for the same trace.
- Task 130 decides the next real-provider local API step: add only an explicit
  LM Studio Responses developer runner/mode
  `assistant_runtime_lmstudio_responses`, with explicit request `model`, no
  preflight enforcement, no generic provider routing, no persistence, no
  sessions/history, and no service daemon behavior.

## Current Foundation Capabilities

Provider Foundation completed:

- approved Pydantic provider-foundation contracts, schema generation, and schema
  version policy
- `ProviderPort` as the minimal provider boundary
- deterministic fake provider plus LiteLLM and LM Studio Responses adapters
- `ProviderRuntime` as the only approved provider construction boundary
- Core `TurnOrchestrator` for the existing provider-foundation turn path
- one-shot CLI provider path and manual provider smoke harness
- minimal telemetry lifecycle through `TelemetrySink`, `NoopTelemetrySink`, and
  `make_trace_event(...)`

Process Readiness has started:

- `HealthCheck` and `VersionInfo` contracts exist
- local `ProcessRuntime` health/version object construction exists
- ProcessRuntime boundary gate completed
- CLI health/version commands exist
- local health/version API app object exists for `GET /health` and
  `GET /version` only
- manual local health/version runner exists for developer smoke on
  `127.0.0.1:8765`
- local bearer-token auth helper protects `/v1/turns`
- protected `/v1/turns` adapter exists with an injected handler boundary only
- RuntimeComposition provides a fake-provider-only handler factory for the
  injected local API handler boundary
- RuntimeComposition provides a developer-only fake `/v1/turns` manual smoke
  runner that composes that handler with the local API runner
- the developer-only fake `/v1/turns` manual smoke has been executed and
  recorded with bounded safe output details
- the future trace exposure decision is recorded: current-process, in-memory,
  telemetry-owned reader/store, injected into Local API, protected by bearer auth
- protected `GET /v1/traces/{trace_id}` now reads only from an explicitly
  injected current-process in-memory telemetry reader
- the developer-only fake `/v1/turns` runner now injects one current-process
  reader/sink so the same process can read the fake turn trace by `trace_id`
- the fake `/v1/turns` plus protected trace-read manual smoke has been executed
  and recorded with bounded safe output details
- no real-provider turn execution composition, service daemon, subprocess
  runtime, or service mode exists
- no persistent trace storage, cross-process lookup, trace search, or streaming
  exists

Assistant-runtime foundation now present:

- approved assistant-envelope models: `InputEvent`, `AssistantTurnInput`,
  `AssistantTurnResult`, and `AssistantFinalResponse`
- assistant-runtime input normalization, result assembly, no-provider runtime
  skeleton, structured-output consumption helpers, and provider-stage skeleton
- Core internal assistant-runtime provider-stage wiring skeleton
- official explicit CLI fake-provider foundation mode via
  `--assistant-runtime-fake-provider`; the Task 107 flag
  `--assistant-runtime-provider-stage-fake` remains a compatibility alias
- CLI now calls RuntimeComposition for both the official fake-provider
  AssistantRuntime foundation mode and the existing provider-foundation turn
  path; CLI no longer imports ProviderRuntime directly
- ProviderRuntime production bridge ownership decision: future real-provider
  AssistantRuntime composition belongs in a separate runtime composition/factory
  layer, not in CLI, Core, AssistantRuntime, ProviderRuntime, ports, or adapters
- `packages.runtime_composition.run_fake_provider_assistant_bridge(...)` proves
  that separate layer with ProviderRuntime-created fake provider only; it calls
  Core's assistant-provider-stage helper and reaches AssistantRuntime provider
  stage behavior without changing default CLI behavior
- `packages.runtime_composition.run_lmstudio_responses_assistant_bridge(...)`
  is the first explicit real-provider-backed AssistantRuntime proof path
- explicit non-default CLI proof mode via
  `--assistant-runtime-lmstudio-responses`; it calls RuntimeComposition and is
  not default, service/API, or product flow
- documented manual live-smoke checklist and bounded failure policy for LM
  Studio unavailable/model rejected, timeout-like, provider error, empty output,
  and malformed response cases
- recorded successful manual live smoke for `qwen3.5-0.8b`, with bounded output
  details and no CI/live-provider validation requirement

Provider structured-output foundation now present:

- boundary-local validation and fallback result model
- adapter-local hooks for LM Studio Responses and LiteLLM
- explicit ProviderRuntime experimental structured-output adapter call path
- internal handoff draft and pressure coverage
- test-only ProviderRuntime-to-AssistantRuntime bridge proof
- no production structured-output bridge or product runtime integration

Validation gates now present:

- workspace/docs/service-placeholder/forbidden-module gates
- project status, file-size, schema-version, library-decision, and library
  research gates
- port, ProviderRuntime, ProcessRuntime, AssistantRuntime, provider structured
  output, runtime composition, local API, runtime ownership, Vaxil boundary,
  and assistant-turn contract gates

Historical governance retained compactly: Task 024 Status and README Drift Cleanup,
Git workflow governance, assistant-turn spine/contract governance, runtime
ownership governance, and library research governance remain accepted.

## Task 102-130 Compact Milestone Summary

- Task 102 wired telemetry-owned structured-output trace safety into
  `packages.telemetry.sinks.make_trace_event(...)`.
- Task 103 added explicit AssistantRuntime structured-output consumption as an
  experimental helper.
- Task 104 proved ProviderRuntime structured-output output can be consumed by
  AssistantRuntime only through test/integration helpers.
- Task 105 added `run_provider_stage_turn(...)`, an AssistantRuntime-owned
  injected provider-stage skeleton.
- Task 106 added `run_assistant_provider_stage_turn(...)`, a Core-owned
  internal wiring skeleton that delegates to AssistantRuntime.
- Task 107 added the opt-in CLI/dev fake-provider vertical slice with
  `--assistant-runtime-provider-stage-fake`, leaving default CLI behavior
  unchanged.
- Task 108 compacted this status file and recorded the next runtime promotion
  decision.
- Task 109 promoted the explicit fake-provider AssistantRuntime CLI path into
  the official foundation mode `--assistant-runtime-fake-provider` while keeping
  the Task 107 flag as a compatibility alias.
- Task 110 decides that a future separate runtime composition/factory layer
  should own production composition between ProviderRuntime and the
  Core/AssistantRuntime assistant-provider-stage path.
- Task 111 adds that first separate layer as a fake-provider-only proof with a
  dedicated runtime composition boundary gate.
- Task 112 wires the official CLI fake-provider foundation mode to the
  RuntimeComposition fake bridge and removes CLI-owned provider construction
  while preserving default CLI behavior.
- Task 113 adds the first RuntimeComposition real-provider proof for
  `lmstudio_responses`, with live execution left to manual provider smoke
  guidance only.
- Task 114 adds the explicit non-default CLI proof flag
  `--assistant-runtime-lmstudio-responses` for that bridge while preserving
  default CLI behavior and the fake-provider foundation mode.
- Task 115 documents manual live-smoke expectations and failure policy for that
  proof mode without adding preflight, routing, retry/fallback, sessions/history,
  model-selection, service/API, or default product behavior.
- Task 116 records a successful manual LM Studio AssistantRuntime CLI proof
  smoke and adds narrow Unicode-safe result printing for that proof-mode output.
- Task 117 adds local health/version API readiness as a dependency-free WSGI app
  object for `GET /health` and `GET /version` only, with a dedicated boundary
  gate and no service listener or turn/provider execution.
- Task 118 adds a manual standard-library loopback runner for that health/version
  app object and smoke documentation, while keeping live server execution out of
  CI and avoiding `/v1/turns`, provider execution, service daemon behavior, or
  product runtime behavior.
- Task 119 classifies health/version as public loopback readiness endpoints and
  future turn/trace/event endpoints as protected. It adds a reusable local
  bearer-token validator for future protected endpoints without wiring auth to
  current health/version behavior or implementing protected endpoints.
- Task 120 decides the protected `/v1/turns` contract, owner split, auth
  enforcement, fake-provider-only first target, response/error behavior, and
  rollback path without implementing the endpoint or adding API execution.
- Task 121 implements the protected fake-provider-only `/v1/turns` adapter with
  auth-before-body validation and stubbed-handler tests only, without adding
  real execution composition.
- Task 122 adds RuntimeComposition-owned fake handler composition for local API
  turns, without making local API import RuntimeComposition or adding LM Studio
  or real-provider API execution.
- Task 123 adds a RuntimeComposition-owned developer-only manual fake
  `/v1/turns` smoke runner with a caller-provided fake/dev token, while keeping
  local API free of RuntimeComposition imports.
- Task 125 records a successful developer-only fake `/v1/turns` manual smoke:
  health/version responded, a valid protected fake turn returned
  `AssistantTurnResult`, auth failures returned safe `AUTH_REQUIRED`, and no
  runtime behavior changed.
- Task 126 decides the future trace exposure path: protected
  `GET /v1/traces/{trace_id}`, local API envelope, telemetry-owned
  current-process in-memory reader/store, no raw trace objects, no persistence,
  and no implementation in this task.
- Task 127 implements the protected fake/local-only trace-read path using
  `packages.telemetry.InMemoryTraceReader` and local API reader injection. The
  endpoint returns safe projection envelopes only; raw `TraceEvent.data`,
  provider payloads, provider response ids, auth material, and secrets are not
  exposed.
- Task 128 integrates fake-turn trace recording only for the manual/dev local
  API fake path. RuntimeComposition passes the injected sink through existing
  fake-provider bridge telemetry, while Local API continues to receive only
  injected handler/reader callables.
- Task 129 records successful manual fake local API turn plus protected trace
  read smoke, with safe current-process trace projections only.
- Task 130 decides that the next real-provider local API step should be an
  explicit LM Studio Responses manual/dev mode only, not a generic provider API
  or service daemon.

## Architecture Health Notes

- The current direction is still foundation-first rather than product-first.
- Telemetry owns redaction/sanitization policy; callers use safe event
  construction instead of owning sanitizer policy.
- Future trace reads must remain telemetry-owned for recording/lookup/safety and
  Local API-owned only for auth/HTTP/JSON adapter behavior.
- AssistantRuntime remains provider-agnostic and does not import Core,
  ProviderRuntime, adapters, ports, CLI, or services.
- Core has a narrow assistant-runtime provider-stage seam but the existing
  `TurnOrchestrator` provider path remains unchanged.
- CLI has one explicit fake-provider AssistantRuntime foundation mode and one
  explicit LM Studio Responses AssistantRuntime proof mode. Both call
  RuntimeComposition; the default provider CLI path remains the
  provider-foundation path and still does not construct providers inside CLI.
- The LM Studio Responses CLI proof has documented manual-smoke success/failure
  expectations; automated validation still does not require live LM Studio.
- The latest manual smoke for that proof path succeeded, but it remains a
  manual developer check and is not part of `run_all_checks.py`.
- Local service readiness now has a health/version API app object and a manual
  loopback runner only. It is not a service daemon.
- Local API auth policy protects `/v1/turns`; health/version behavior remains
  public and unchanged.
- Local API auth policy also protects `GET /v1/traces/{trace_id}` when a trace
  reader is explicitly injected.
- The `/v1/turns` adapter is protected fake-provider-only by request envelope:
  it accepts a local envelope carrying `AssistantTurnInput`, returns
  `AssistantTurnResult`, and delegates only to an injected handler.
- RuntimeComposition now owns the fake injected handler factory for local API
  turns and routes it through the existing fake-provider bridge path.
- RuntimeComposition also owns the developer-only fake-turns smoke runner that
  injects that handler into the local API runner. Its manual fake smoke has
  been recorded, and it now shares an in-memory trace reader between fake turn
  recording and protected trace reads. It is not a service daemon or production
  token lifecycle.
- ProviderRuntime remains the only approved production provider construction
  boundary. RuntimeComposition may call it for approved bridge proofs while
  importing no concrete adapters and owning no routing/session/history policy.
- RuntimeComposition is now the approved CLI composition dependency for the
  existing provider-foundation path and the fake-provider AssistantRuntime
  foundation mode. Core, AssistantRuntime, and ProviderRuntime still do not
  import RuntimeComposition.
- RuntimeComposition also owns one real-provider AssistantRuntime proof function
  for `lmstudio_responses`, now reachable from an explicit CLI proof flag. It
  is not a router, session manager, retry/fallback owner, model-selection owner,
  API-key policy owner, or product orchestrator.
- Task 130 unlocks only a future explicit LM Studio Responses local API
  implementation pack; it does not itself implement real-provider `/v1/turns`.
- `PROJECT_STATUS.md` is no longer a chronological task log; historical detail
  belongs in package READMEs, tests, task reports, and git history.

## Explicit Non-Goals And Blocked Work

Blocked without a separate approved task spec:

- default CLI behavior changes
- ProviderRuntime production bridge into AssistantRuntime
- real provider promotion for assistant-runtime turns
- Core normal orchestration replacement
- service/API/HTTP/WebSocket/subprocess runtime or daemon behavior
- real-provider execution composition behind `/v1/turns` except the exact
  Task 130-approved LM Studio Responses implementation pack
- generic provider local API mode and any non-LM-Studio first provider mode
- telemetry persistence/logging sinks, cross-process trace storage, trace search,
  and trace streaming
- contract or port promotion
- tools, memory, UI, voice, desktop, vision, proactive behavior
- sessions, hidden history, routing, retry/fallback, API keys, or model routing
- structured-output handoff promotion into a public contract

A roadmap item, package README note, status recommendation, or task number is
not implementation permission.

## Next Implementation Task

Next work unlocked by Task 130: add an explicit developer-only LM Studio
Responses local API turns runner/handler pack for
`assistant_runtime_lmstudio_responses`, using explicit request `model`, bearer
auth, injected handler composition, and the same current-process
`InMemoryTraceReader` pattern as fake mode.

Do not add persistent telemetry, cross-process lookup, WebSocket/event streams,
service daemon behavior, generic provider API mode, sessions/history, routing,
retry/fallback, model-selection, API-key policy, tools, memory, UI, voice,
desktop, vision, proactive behavior, or default CLI changes without another
explicit task.
