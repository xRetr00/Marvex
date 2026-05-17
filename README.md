# Marvex

<p align="center">
  <img src="assets/logo.png" alt="Marvex logo" width="300" />
</p>

Marvex is a service-ready modular desktop system. It starts as a Python Core
Service with a CLI client, provider adapters, and telemetry, then grows into a
process-ready desktop application where major modules can be replaced, disabled,
or moved into subprocesses.

`PROJECT_STATUS.md` is authoritative for the current phase and allowed work.
Implementation is allowed only through approved task slices with contracts,
tests, validation scripts, and final reports.

Agents should start orientation with `docs/SYSTEM_MAP.md`,
`docs/MODULE_INDEX.md`, and `docs/AGENT_CONTEXT_RULES.md` before broad source
discovery.

AI agents must run the validation scripts before finishing any task, including a
one-line hotfix. The required command is:

```powershell
python scripts/run_all_checks.py
```

The user is not expected to review code correctness. Agents must not rely on
user code review as a safety mechanism. Every implementation step must be
controlled by contracts, task specs, tests, validation scripts, and a final
report.

## Current Implementation

Provider Foundation is complete:

- Pydantic contract models and JSON schema generation.
- `ProviderPort` as a tiny contract-only provider boundary.
- Deterministic `FakeProvider`.
- `LiteLLMProvider` isolated behind the provider adapter boundary.
- `LMStudioResponsesProvider` isolated behind the provider adapter boundary and
  using the OpenAI Python SDK against LM Studio's OpenAI-compatible Responses API.
- `ProviderRuntime` as the only approved provider creation boundary.
- `TurnOrchestrator` for minimal Core turn orchestration through `ProviderPort`.
- Minimal telemetry lifecycle events through `TelemetrySink` and
  `NoopTelemetrySink`.
- One-shot CLI vertical slice.
- Local CLI health/version commands for process readiness reporting.
- Manual provider smoke harness with fake, LiteLLM, and LM Studio targets.

Process Readiness has started:

- Health/version contracts exist as `HealthCheck` and `VersionInfo`.
- A local `ProcessRuntime` health/version provider builds those contract objects
  from explicit in-memory configuration.
- The ProcessRuntime boundary gate keeps local health/version object
  construction isolated until an approved integration task.
- The CLI can expose local health/version contract objects without starting a
  service.
- A dependency-free local health/version API app object exists for `GET /health`
  and `GET /version` only.
- A manual developer-only local runner can host that app object on
  `127.0.0.1:8765` for health/version smoke verification. No service daemon,
  provider execution, WebSocket, session/history, or product service behavior
  exists.
- Local API auth policy is defined for future protected endpoints:
  health/version stay public on loopback, while future turn/trace/event
  endpoints must use `Authorization: Bearer <local-token>`.
- `POST /v1/turns` now exists only as a protected HTTP/auth/JSON adapter:
  fake-provider request envelope, injected handler boundary, and
  `AssistantTurnResult` serialization. RuntimeComposition remains the future
  execution composition owner and is not imported by the API.
- RuntimeComposition now provides a fake-provider-only local API turn handler
  factory that can be injected into the app for controlled fake execution.
- A developer-only RuntimeComposition smoke runner can start local API fake
  `/v1/turns` execution with a caller-provided fake/dev bearer token.
- The developer-only fake `/v1/turns` smoke has been run and recorded with
  bounded safe output details; it remains manual-only and fake-provider-only.
- A protected local-only `GET /v1/traces/{trace_id}` adapter can now read from
  an explicitly injected current-process in-memory telemetry reader. It does not
  add persistence, service daemon behavior, WebSocket/events, real-provider API
  mode, sessions/history, or default CLI changes.
- The developer-only fake `/v1/turns` manual runner now shares one
  current-process in-memory telemetry reader between fake turn recording and
  protected trace reads.
- A developer-only RuntimeComposition runner can also inject an explicit LM
  Studio Responses `/v1/turns` handler and the same current-process trace
  reader pattern. The provider token path is LM Studio-only through
  ProviderRuntime config and `MARVEX_LMSTUDIO_API_KEY`; the request body, Local
  API, Core, AssistantRuntime, telemetry, and default CLI remain provider-token
  blind. Token-backed live success is still deferred until the user provides a
  local LM Studio API token.

Git workflow governance exists:

- Normal small and medium tasks run directly on `main`.
- Branches require explicit approval before creation.
- Task flow is plan, approval, implementation, validation, commit, and push.

## Current Boundary

Allowed now:

- Documentation, templates, and validation scripts.
- README/status/library/schema governance cleanup.
- Approved task slices only.
- Service placeholder READMEs.

Forbidden now:

- Unapproved product behavior changes.
- Provider behavior changes outside approved adapter tasks.
- CLI behavior changes outside approved API tasks.
- Telemetry runtime behavior changes outside approved telemetry tasks.
- UI code.
- Tool execution.
- Memory systems.
- Voice, vision, desktop context, proactive behavior.

A roadmap entry, task id, or placeholder README is not permission to implement.

No turn endpoint exists yet as a generic, default, or product real-provider
execution surface. The only real-provider local API path is the explicit
developer-only LM Studio Responses runner.
No persistent trace storage, cross-process trace lookup, or trace streaming
exists yet.
No service daemon exists yet.
No subprocess runtime or service mode exists yet.
The local health/version API runner is manual smoke only, not product service behavior.
The local fake-turns API runner is also manual smoke only and fake-provider only.

Current AssistantRuntime CLI foundation modes are explicit and non-default:
`--assistant-runtime-fake-provider` for the deterministic fake path and
`--assistant-runtime-lmstudio-responses` for the LM Studio Responses proof path.
The real-provider proof remains opt-in only and does not approve service/API or
product behavior changes. Live LM Studio use is manual smoke only and is not
required by pytest or `scripts/run_all_checks.py`; the latest recorded manual
smoke for the proof path succeeded against a local LM Studio model.

## Capability Platform Foundation

Capability Platform Foundation adds `packages/capability_runtime` plus disabled/proof adapter seams under `packages/adapters/capabilities`. It establishes policy-governed capability proposals, context delivery, compaction, loop guards, fake deterministic dispatch proof, and safe lifecycle summaries without real tool execution.
