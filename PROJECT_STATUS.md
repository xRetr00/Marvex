# Project Status

current_phase: local_runtime_api_foundation_complete

implementation_status: local_runtime_api_foundation_complete

accepted_docs: true

current_governance_gate:

Local Runtime API Foundation Complete

## Validation Baseline

Latest full validation baseline from Task 145:

- `python scripts\run_all_checks.py` -> PASS all validation checks passed
- `python -m pytest -q` -> 738 passed, 1 skipped

## Local Runtime API Foundation Completion State

The Local Runtime API Foundation is complete as a future Shell/CLI-facing local
service foundation. A future client can locate token-redacted loopback metadata,
check public `/health` and `/version`, and call protected `/v1/turns` plus
`GET /v1/traces/{trace_id}` through explicit bearer-auth paths. Discovery files
remain local-user-scoped and never contain raw bearer tokens; protected calls
require a private startup token handoff outside public metadata. Current trace
reads remain same-process, auth-protected, telemetry-owned safe projections.
Local API stays HTTP/auth/JSON only, local service startup owns startup/token and
discovery metadata, RuntimeComposition stays explicit composition only, and
Core/ProviderRuntime remain token/lifecycle/discovery blind.

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
- Task 131 implements that explicit developer-only runner/handler path. The
  manual runner injects one current-process `InMemoryTraceReader` for both
  telemetry recording and protected trace reads. Local API still receives only
  injected handler/reader callables.
- Task 132 records a manual LM Studio local API smoke. The local API runner,
  auth, mapped provider-error response, and protected trace read worked
  end-to-end on 2026-05-16, but LM Studio returned `AuthenticationError`
  because the current local server requires a valid local API token and rejected
  the placeholder SDK key. No runtime code changed.
- Task 133 decides the LM Studio token path as docs-only: provider credentials
  belong to ProviderRuntime plus the LM Studio adapter config, may be passed by
  the explicit developer-only RuntimeComposition runner, and must not enter
  Local API, Core, AssistantRuntime, request envelopes, traces, logs, or errors.
- Task 134 implements the narrow LM Studio-only token path:
  `ProviderRuntimeConfig.lmstudio_responses_api_key` maps to
  `LMStudioResponsesProviderConfig(api_key=...)`, and the developer-only LM
  Studio local API runner reads `MARVEX_LMSTUDIO_API_KEY` without printing or
  recording its value. Local API, Core, AssistantRuntime, telemetry, default
  CLI behavior, request bodies, and `provider_options` remain provider-token
  blind.
- Task 136 records a token-backed LM Studio local API smoke. With the provider
  token supplied from local environment only, `/health`, `/version`, protected
  `/v1/turns`, and protected `GET /v1/traces/{trace_id}` succeeded for
  `qwen3.5-0.8b`. Trace output exposed only safe current-process projections;
  missing/wrong auth for both protected routes returned `401 AUTH_REQUIRED`.
- Task 137 decides the future service lifecycle and local bearer token startup
  boundary without implementation. A future service runner/startup boundary owns
  generated local bearer token creation, explicit startup/shutdown reporting,
  and any local-user-scoped discovery metadata. Local API remains HTTP/auth/JSON
  only, RuntimeComposition remains composition-only, Core remains service-token
  blind, and trace reads remain auth-protected.
- Task 138 implements the first `packages.local_service_startup` foundation. It
  generates a high-entropy in-memory local bearer token, produces safe public
  startup metadata, defines explicit startup/shutdown semantics, and keeps
  discovery-file writing outside the foundation object itself. Daemon
  supervision, Local API handler integration, RuntimeComposition service
  ownership, Core lifecycle coupling, and ProviderRuntime credential policy
  stay blocked.
- Task 139 adds a narrow Local API service-runner startup proof. It generates
  the local bearer token through `packages.local_service_startup`, injects that
  raw token only into the existing Local API runner call, and prints only safe
  public startup metadata. Discovery-file writes were still blocked at Task
  139. Daemon supervision, auto-restart, RuntimeComposition service ownership,
  generic provider routing, persistent telemetry, sessions/history, and
  WebSocket/events remain blocked.
- Task 140 records a bounded manual smoke for the startup-proof runner:
  `/health` and `/version` returned HTTP 200 on loopback, missing/wrong
  `/v1/turns` auth returned HTTP 401, startup metadata reported token presence
  only, and stdout did not include `local_auth_token`.
- Task 141 decides the first local client discovery path before implementation:
  future discovery metadata may be a local-user-scoped JSON file containing only
  loopback connection metadata and token presence, never raw tokens. Protected
  endpoint access still requires an explicit private token handoff outside that
  file. Discovery-file writes, readers, cleanup, and permissions remain future
  narrow implementation tasks.
- Task 142 implements the first safe discovery metadata writer in
  `packages.local_service_startup`. It writes only token-redacted loopback
  startup metadata under an explicit local-user root, rejects out-of-scope paths
  and remote bind metadata, and does not write bearer tokens or provider
  credentials. Reader/client helpers, cleanup, startup-runner integration, and
  token handoff remain future narrow tasks.
- Task 143 adds the matching safe discovery metadata reader. It reads only
  local-user-scoped JSON metadata, rejects unsafe/raw-token fields and remote
  bind metadata, and returns safe service location/token-presence data for a
  future client without becoming a launcher, registry, token store, or retry
  layer.
- Task 144 wires the approved discovery metadata writer into the startup proof
  runner only when an explicit discovery file path is supplied. The runner
  writes safe loopback metadata, rejects missing or out-of-scope discovery file
  paths, keeps the raw bearer token out of startup output and discovery files,
  and does not add daemon supervision, hidden auto-start, token storage, cleanup,
  client calls, provider routing, retry/fallback, model selection,
  sessions/history, WebSocket/events, or persistent telemetry.
- Task 145 adds `packages.local_api_client` as a narrow future Shell/CLI
  connection proof helper. It reads safe discovery metadata, validates loopback
  and token-redaction rules, calls public readiness endpoints without auth, and
  calls protected `/v1/turns` plus `GET /v1/traces/{trace_id}` only when the
  caller supplies the local bearer token per request. The discovery file still
  never stores the raw token; private token handoff remains outside public
  discovery metadata.

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
- local service startup foundation can now generate a local bearer token and
  safe startup metadata without starting a service or writing discovery files
- local service startup can now run a narrow Local API service-runner startup
  proof that injects the generated token into the existing Local API runner and
  prints safe metadata only
- local service startup can now write safe local-user-scoped discovery metadata
  without raw tokens, remote bind addresses, provider credentials, or handler
  configuration
- the Local API service-runner startup proof can now explicitly write that safe
  discovery metadata through `--discovery-file <path>` while still passing the
  raw generated token only to the Local API runner call
- a narrow future Shell/CLI client helper can now load safe discovery metadata
  and make explicit loopback JSON calls while requiring per-call bearer token
  input for protected turn and trace endpoints
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
  output, runtime composition, local API, local API client, runtime ownership,
  Vaxil boundary, and assistant-turn contract gates

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
- Task 131 adds that explicit manual/dev LM Studio Responses local API runner
  and handler while preserving fake mode and local API boundaries.

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
- Task 131 implements only that explicit developer runner/handler path; it is
  not default, generic provider routing, model selection, preflight enforcement,
  retry/fallback, session/history, or service daemon behavior.
- `PROJECT_STATUS.md` is no longer a chronological task log; historical detail
  belongs in package READMEs, tests, task reports, and git history.

## Explicit Non-Goals And Blocked Work

Blocked without a separate approved task spec:

- default CLI behavior changes
- ProviderRuntime production bridge into AssistantRuntime
- real provider promotion for assistant-runtime turns
- Core normal orchestration replacement
- service/API/HTTP/WebSocket/subprocess runtime or daemon behavior
- real-provider execution composition behind `/v1/turns` beyond the explicit
  Task 131 developer-only LM Studio Responses runner/handler path
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

The Local Runtime API Foundation is complete. Next work should be a separately
approved foundation slice. Do not add raw bearer-token storage, daemon
supervision, auto-restart, generic provider routing, persistent telemetry,
sessions/history, WebSocket/events, retry/fallback, model selection, or broader
token lifecycle machinery without another explicit task.

Do not add persistent telemetry, cross-process lookup, WebSocket/event streams,
service daemon behavior, generic provider API mode, sessions/history, routing,
retry/fallback, model-selection, API-key policy, tools, memory, UI, voice,
desktop, vision, proactive behavior, or default CLI changes without another
explicit task.
