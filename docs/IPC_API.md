# IPC API

Marvex will use localhost HTTP, WebSocket, and JSON communication between the app shell and services in a future process/runtime phase.

Provider Foundation currently has JSON contracts and a local in-memory
health/version object provider only. Task 020 does not implement HTTP servers,
endpoints, subprocesses, daemons, or networking.

Task 026 defines future endpoint contracts only. It does not implement an HTTP
server, service daemon, subprocess runtime, socket listener, framework
dependency, or service mode.

No HTTP implementation exists in Task 026.

Task 117 adds a dependency-free local WSGI app object for `GET /health` and
`GET /version` only. It is a service/API readiness foundation, not a service
daemon. It does not start a listener, implement `/v1/turns`, enforce local auth,
open WebSockets, expose traces, call providers, call RuntimeComposition, or run
Core/AssistantRuntime turn behavior. Future listener/auth/service lifecycle work
still requires a separate approved task.

Task 118 adds a manual developer-only local runner for that health/version app
object. The runner binds to `127.0.0.1:8765` by default and remains manual
smoke only. It does not implement `/v1/turns`, auth, WebSocket, trace API,
provider execution, assistant turn execution, service daemon management, or
product behavior.

UI/API/WebSocket contracts for future web, native orb, presence, trace viewer,
settings, or voice/face visualization surfaces are explicit future tasks. Task
085 documents frontend ownership boundaries in `docs/FRONTEND_BOUNDARY.md`; it
does not implement UI runtime, HTTP endpoints, WebSocket streams, backend API
behavior, or product behavior.

## Localhost Security Defaults

- Services must bind to `127.0.0.1` by default.
- Binding to `0.0.0.0`, LAN addresses, or remote interfaces is forbidden unless a future remote mode is explicitly approved.
- Future remote mode must be explicit opt-in, documented by RFC, and covered by authentication, authorization, transport security, and threat-model review.
- The future server must require a random local auth token generated at startup or a clearly marked dev token for local development.
- Local health/version readiness endpoints are public on the loopback interface
  so shell/client code can check readiness before protected API setup.
- Future turn submission, trace access, and event endpoints are protected.
- Protected endpoints must use `Authorization: Bearer <local-token>`.
- The local token source is future service startup configuration or a generated
  startup token. Token generation, discovery, rotation, and storage remain
  future service-runtime work.
- Clearly fake dev tokens may be used only by explicit local development
  commands/tests and must not become defaults.
- The auth token must not be logged by default.
- Missing or invalid auth must return an `ErrorEnvelope` with `code:
  "AUTH_REQUIRED"`.
- Browser-facing clients must use restrictive CORS and origin checks. Default allowed origins are local app origins only.
- WebSocket clients must authenticate before receiving events.
- Trace data access requires the same local auth token as turn submission.
- Trace endpoints must not expose traces across sessions unless a future explicit session contract allows it.
- Ports must default to configurable local ports. If a preferred port is busy, the service may choose an available local port and report it through startup output or a local discovery file.
- Port selection must not silently expose a service on a remote interface.

## Local Service Startup And Token Discovery Decision

Decision title: Task 137 Service Lifecycle And Local Token Startup Boundary.

Status: decision-only. No daemon, token generation, token storage, discovery
file, supervisor, or service runner implementation is approved by this section.

Current context: Task 136 proved the explicit developer-only LM Studio Local
API runner can handle public `/health` and `/version`, protected `/v1/turns`,
and protected `GET /v1/traces/{trace_id}` with a locally supplied provider
token. That smoke used a caller-provided fake/dev local bearer token. It did not
implement production local token startup behavior.

Decision:

- Future generated local bearer token creation belongs to a future service
  runner/startup boundary, not ProviderRuntime, Core, AssistantRuntime,
  RuntimeComposition bridge helpers, Local API request handlers, provider
  adapters, telemetry, CLI proof commands, or contracts.
- Local API owns only HTTP/auth/JSON enforcement for protected endpoints. It
  may validate a token value supplied by startup composition, but it must not
  generate, persist, discover, rotate, print, or supervise that token.
- RuntimeComposition may compose explicitly approved handlers/runners, but it
  must not become a daemon supervisor, token lifecycle manager, service
  registry, routing brain, retry/fallback owner, model selector, or
  long-running process manager.
- Core remains provider-agnostic and service-lifecycle agnostic. Core must not
  know local bearer token mechanics or service discovery details.
- Future service startup output may report the local API URL, token presence,
  and where an authorized local client can discover connection metadata, but it
  must not print the raw local bearer token by default.
- Future local service discovery should use either explicit CLI-provided config
  or a local-user-scoped discovery file. The first implementation must choose
  one narrow path explicitly. Any discovery file must be readable only by the
  local user where platform support allows, must describe only loopback
  connection metadata, and must not expose remote interfaces.
- Trace access remains protected by the same local bearer token as turn
  submission. Persistent trace storage and cross-process trace lookup remain
  blocked until a separate telemetry-owned task approves them.
- Future service startup and shutdown must be explicit, bounded, traceable, and
  process-ready. Hidden auto-start, hidden global state, background CLI daemon
  behavior, and automatic restart loops remain blocked unless a later service
  lifecycle task approves them with telemetry and shutdown rules.

Blocked until separate implementation tasks: token storage, service daemon
lifecycle, supervisor behavior, auto-restart, remote binding, WebSocket/events,
persistent telemetry, sessions/history, generic provider routing,
retry/fallback, model selection, memory, tools, UI, voice, desktop, vision, and
proactive behavior.

Task 138 implementation note: `packages.local_service_startup` adds the first
startup foundation object model. It can create a high-entropy in-memory local
bearer token and safe public startup metadata with `schema_version`, `service`,
`base_url`, `bind_host`, `port`, `auth_required`, `auth_token_present`,
`token_value_logged`, `discovery_mode`, optional `discovery_file_path`,
`process_id`, `started_at`, `contract_versions`, and `warnings`. The raw token
exists only on the in-memory startup result for future runner use; public
metadata reports presence only and always sets `token_value_logged: false`.
Discovery file writing, token storage, daemon lifecycle, and service integration
remain blocked.

Task 139 implementation note: `packages.local_service_startup` adds a narrow
Local API service-runner startup proof. It calls the existing Local API runner
with a generated local bearer token and prints only safe public metadata. The
metadata reports token presence but not the raw token. Discovery-file writes,
token storage, daemon lifecycle, auto-restart, generic provider routing,
persistent telemetry, sessions/history, WebSocket/events, and broader token
lifecycle management remain blocked.

Task 141 discovery decision: the first future discovery implementation should be
a local-user-scoped JSON metadata file written by `packages.local_service_startup`.
The file may contain only safe loopback connection fields already present in
public startup metadata, plus schema/service/version/process fields and warning
state. It must not contain the raw local bearer token, provider credentials,
environment values, prompts, traces, sessions, history, remote bind addresses,
or handler/provider configuration. Protected endpoint access still requires an
explicit private token handoff outside the discovery file. The first writer must
reject non-loopback metadata and avoid discovery writes unless explicitly
requested by startup config; a reader/client helper may only read this safe
metadata and must not become a token store, service registry, launcher, daemon,
retry/fallback layer, model selector, or cross-process trace lookup.

Task 142 implementation note: `packages.local_service_startup.discovery` writes
safe discovery metadata only when given an explicit path under a local-user
root. It serializes the public startup metadata, rejects out-of-scope paths and
non-loopback metadata, best-effort restricts file permissions, and never writes
the raw local bearer token. Reader/client helpers and cleanup remain future
tasks.

Task 143 implementation note: the same discovery module can now read safe
local-user-scoped metadata for a future client. The reader validates local-user
scope, JSON object shape, loopback URL, and token-redaction rules before
returning metadata. It does not read tokens, launch services, clean up files,
select providers, retry connections, or perform protected Local API calls.

Task 144 implementation note: the startup proof runner can now explicitly write
that safe discovery metadata by passing `--discovery-file <path>`. The path is
validated under the local-user root, the file contains only token-redacted
loopback startup metadata, and the raw bearer token is still injected only into
the in-process Local API runner call. No daemon supervision, hidden auto-start,
token storage, cleanup loop, client connection helper, provider routing,
retry/fallback, model selection, sessions/history, WebSocket/events, or
persistent telemetry is added.

Task 145 implementation note: `packages.local_api_client` adds the first narrow
future Shell/CLI connection helper. It reads safe discovery metadata, validates
loopback/token-redaction rules, calls public readiness endpoints without auth,
and calls protected `/v1/turns` plus `GET /v1/traces/{trace_id}` only when the
caller supplies the local bearer token per request. The discovery file still
does not contain the token; future clients must receive the raw token through a
private startup handoff outside public metadata. The helper does not launch or
supervise services, cache tokens, manage sessions/history, retry/fallback,
select models, route providers, persist telemetry, or own UI behavior.

Completion note: the Local Runtime API Foundation now covers explicit startup,
safe discovery metadata, public loopback readiness, protected turn submission,
protected current-process trace reads, and a narrow client connection proof.
Daemon supervision, raw token storage, remote binding, sessions/history,
WebSocket/events, persistent telemetry, generic provider routing, retry/fallback,
model selection, memory, tools, UI, voice, desktop, vision, and proactive
behavior remain blocked.

## Future HTTP Endpoint Contracts

The following endpoints are future explicit tasks. Their response contracts
exist now and can be built locally from explicit in-memory config, but no
endpoint implementation exists in Task 020 or Task 026.

These endpoint contracts are localhost-only by default. Task 117 implements only
the health/version WSGI app object without selecting a Python HTTP framework.
Task 118 adds a standard-library manual runner for health/version smoke only.
Task 119 keeps `/health` and `/version` public on loopback and defines auth for
future protected endpoints only. Task 121 wires that auth boundary only to the
protected fake-provider `/v1/turns` HTTP/auth/JSON adapter with an injected
handler. Trace access and event endpoints remain future protected endpoints.

HTTP status mapping:

- `200`: success response body.
- `4xx`: auth, client, or request/contract error response body.
- `5xx`: service or internal error response body.

All error response bodies must use `ErrorEnvelope`.

### GET /health

Localhost-only public readiness endpoint.

Request body: none.

Success: `200` with `HealthCheck`.

Error: `4xx` or `5xx` with `ErrorEnvelope`.

`HealthCheck` currently has no timestamp field. `uptime_seconds` is future
runtime uptime in non-negative seconds. `dependencies` is a JSON object only;
there is no approved nested dependency-status schema yet. The endpoint must not
probe providers or dependencies until a future dependency-status contract is
approved.

### GET /version

Localhost-only public readiness endpoint.

Request body: none.

Success: `200` with `VersionInfo`.

Error: `4xx` or `5xx` with `ErrorEnvelope`.

`VersionInfo` currently has no timestamp field. `contract_versions` and `build`
are JSON objects; detailed build metadata shape is future contract work.

### POST /v1/turns

Decision title: Task 130 Real-Provider Local API Turns Decision.

Status: implemented for the default fake mode and, as of Task 131, for an
explicit developer-only LM Studio Responses runner mode. The route is protected
by bearer auth, parses a local adapter envelope carrying `AssistantTurnInput`,
and delegates to an injected
`Callable[[LocalTurnRequestEnvelope], AssistantTurnResult]`. Local API still
does not import RuntimeComposition, Core, AssistantRuntime, ProviderRuntime,
adapters, telemetry implementation modules, CLI apps, services, or SDKs.

Current context after Task 129: fake `/v1/turns` plus protected
`GET /v1/traces/{trace_id}` smoke succeeded in one current process. The fake
turn returned `trace_id`, `turn_id`, and a fake provider ref; trace read
returned five safe projected in-memory events; missing/wrong trace auth returned
`401 AUTH_REQUIRED`.

Options considered:

- Block real-provider API until service daemon/token lifecycle: rejected for the
  first developer-only proof because the existing explicit local runner, bearer
  auth boundary, and in-memory trace reader are enough for a bounded manual
  smoke path.
- Add LM Studio Responses API mode now: recommended, but only as a separate
  explicit opt-in implementation task and manual runner.
- Add preflight first: rejected. Provider reachability/model probing would risk
  turning diagnostics into model-selection or availability policy.
- Add real-provider manual-runner mode only: recommended first shape.
- Add generic provider mode: rejected. It would introduce routing,
  provider-specific API policy, model selection, or API-key policy too early.

Task 131 implementation path: one narrow RuntimeComposition handler/runner now
supports LM Studio Responses local API turns. It uses explicit execution mode
`assistant_runtime_lmstudio_responses`, keeps `assistant_runtime_fake_provider`
unchanged, and composes through RuntimeComposition outside `packages.local_api`.

Request envelope decision: reuse the existing local adapter envelope. For the
LM Studio mode, `execution_mode` must be
`assistant_runtime_lmstudio_responses`, `assistant_turn_input` must validate as
`AssistantTurnInput`, `model` is required and non-empty, `instructions` and
`previous_response_id` are explicit nullable fields, and `provider_options`
remains `{}` until a later task approves keys. No provider payloads, raw
prompts, sessions/history, tool data, memory data, auth material, or trace
payloads may be carried in metadata.

Response contract decision: successful handler completion still returns
`AssistantTurnResult`; request/auth/transport failures still return top-level
`ErrorEnvelope`. There is no top-level `provider_response_id`; provider identity
may appear only through assistant-envelope reference fields such as
`provider_turn_refs`.

Auth decision: `/v1/turns` remains protected by
`Authorization: Bearer <local-token>`. Auth must run before body validation or
handler invocation. Missing, malformed, unconfigured, or wrong tokens return
`401 AUTH_REQUIRED` without echoing token material. `/health` and `/version`
remain public loopback readiness endpoints.

Provider-token distinction: the local bearer token protects Marvex local
endpoints only. LM Studio provider API tokens are not local API auth tokens and
must not be accepted in the `/v1/turns` request envelope, `provider_options`, or
headers consumed by `packages.local_api`. Provider credentials belong to the
provider adapter construction path through ProviderRuntime and any explicit
RuntimeComposition developer-runner config approved for that provider.

Model requirement decision: the API supports only caller-provided explicit
`model`. It must not default, discover, select, route, or rewrite models.

Preflight decision: no automatic preflight is required before first real-provider
local API mode. Failure behavior should remain provider-stage mapped errors from
the existing RuntimeComposition/Core/AssistantRuntime path. Future preflight, if
approved, must be observe-only and must not block or select providers by
default.

Trace recording/read decision: the real-provider manual runner should use the
same explicit current-process `InMemoryTraceReader` model as fake mode. One
instance may be injected as the handler telemetry sink and as the trace reader
for `GET /v1/traces/{trace_id}`. Telemetry owns recording, lookup, and safe
projection. No persistence, global trace store, search, streaming, or
cross-process lookup is allowed.

Failure behavior decision: tests for the implementation pack must cover auth
missing/malformed/wrong, invalid JSON/request fields, unsupported execution
mode, missing/blank model, non-empty provider options, handler unavailable,
handler exception sanitization, provider unavailable, provider timeout-like
failure, provider error response, empty provider output, malformed provider
response, and trace read not found/reader failure. Failure bodies must not expose
raw provider payloads, exception details, bearer tokens, secrets, prompts, or
provider response ids.

Manual smoke requirement: the runner is developer-only and shaped like
`python -m packages.runtime_composition.local_api_lmstudio_responses_runner --dev-token <fake-dev-token>`.
With LM Studio already running and a model loaded, submit a protected
`POST /v1/turns` using `assistant_runtime_lmstudio_responses`, extract
`trace_id`, then read protected `GET /v1/traces/{trace_id}` and verify safe
projected current-process events. This smoke remains outside CI and
`run_all_checks.py`.

Allowed dependency direction:

```text
HTTP client
  -> packages.local_api protected endpoint adapter
    -> injected turn handler
      -> RuntimeComposition-owned LM Studio Responses handler/runner
        -> Core assistant-provider-stage helper
          -> AssistantRuntime provider-stage helper
        -> ProviderRuntime approved provider factory
```

Forbidden dependency direction: `packages.local_api` must not import
RuntimeComposition/Core/AssistantRuntime/ProviderRuntime/adapters. Core and
AssistantRuntime must not import RuntimeComposition or ProviderRuntime/adapters.
ProviderRuntime must not import Core or AssistantRuntime. RuntimeComposition
must not import concrete adapters, own provider routing, session/history,
retry/fallback, model-selection, API-key policy, trace lookup, HTTP parsing, or
auth policy.

What remains blocked: generic provider mode, additional provider modes, service
daemon lifecycle, token generation or discovery, preflight enforcement,
persistence, cross-process traces, WebSocket events, sessions/history, routing,
retry/fallback, model selection, API-key policy, tools, memory, UI, voice,
desktop, vision, and proactive behavior.

Task 131 implementation note:

- RuntimeComposition adds `create_local_api_lmstudio_turn_handler(...)`.
- The manual runner injects that handler plus one `InMemoryTraceReader`.
- Local API accepts the LM Studio execution mode only when that mode is
  explicitly injected by the runner.
- No generic provider router, model selector, preflight probe, retry/fallback,
  session/history store, persistent trace store, or service daemon is added.

Rollback path: if this decision proves too broad, do not implement the next
pack, keep `/v1/turns` fake-only, and keep real-provider execution available
only through the existing explicit CLI proof mode.

### GET /v1/traces/{trace_id}

Status: implemented in Task 127 as a protected fake/local-only trace-read
adapter. Requires `Authorization: Bearer <local-token>`.

Ownership: `packages.telemetry` owns current-process event recording, lookup,
and read-time safety through an explicitly constructed in-memory reader.
`packages.local_api` owns only bearer auth, route parsing, trace-id validation,
status mapping, and JSON serialization. The reader is injected into the app;
there is no hidden global trace store.

Response envelope: `schema_version`, `trace_id`, `scope: "current_process"`,
`source: "in_memory"`, `events`, `event_count`, and `truncated`. Events are
sanitized projections, not raw `TraceEvent` objects. Projection fields are
`trace_id`, optional safe `turn_id`, `event_id`, `timestamp`, `stage`, `level`,
bounded safe `message`, and safe status/error/finish/service/usage fields.
`TraceEvent.data` is not serialized.

Allowed fields: trace/turn/event ids, timestamps, stages, levels, bounded safe
messages, status enums, error codes, finish reasons, service names, and
aggregate usage/counts. Forbidden fields: raw prompts/messages/conversations,
provider payloads/previews, parsed payloads, stack traces, auth/API keys,
secrets, environment variables, file contents, session/history bodies, tool or
memory data, provider response ids, unsanitized `TraceEvent.data`, and events
outside the current injected store scope.

Error behavior: missing/invalid auth -> `401 AUTH_REQUIRED`; invalid or blank
trace id -> `400 VALIDATION_ERROR`; unknown current-process trace id ->
`404 NOT_FOUND` with safe reason `trace_not_found`; missing injected reader ->
`503 SERVICE_UNHEALTHY`; unexpected reader failure -> `500 INTERNAL_ERROR`.
Auth is checked before trace-id lookup.

Scope rule: the first trace endpoint may read only events recorded by the
current local process and injected in-memory store, not disk, other processes,
old runner invocations, or cross-session/global caches.

Blocked: persistent telemetry, trace search, cross-process lookup, streaming,
service daemon lifecycle, real-provider API mode, sessions/history, routing,
retry/fallback, model-selection, API-key policy, tools, memory, UI, voice,
desktop, vision, and proactive behavior.

Rollback path: remove the route branch and reader injection. No Core,
AssistantRuntime, ProviderRuntime, RuntimeComposition, adapter, CLI, or
`/v1/turns` shape changes should be needed.


### WS /v1/events

Future protected endpoint. Requires `Authorization: Bearer <local-token>`
before event delivery.

Streams `TraceEvent` records and later service lifecycle events.

Requires local auth before event delivery. Must close unauthenticated or wrong-origin connections.

## Future Worker Envelope

Future workers use a JSON-RPC-style envelope:

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "method": "worker.method",
  "params": {},
  "trace_id": "trace-id",
  "version": "contract-version"
}
```

Error responses must use `ErrorEnvelope`.

- Every request carries `trace_id`.
- Every response declares schema version.
- Every future service exposes health and version.
- No service may return unstructured exceptions.
- No module may depend on in-process calls if it is defined as process-ready.
