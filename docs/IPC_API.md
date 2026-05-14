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

Decision title: Local API `/v1/turns` contract and ownership decision after
Task 119.

Current context: Task 117 added a dependency-free WSGI app object for
`GET /health` and `GET /version`. Task 118 added a manual loopback runner for
those public readiness endpoints. Task 119 defined the local bearer-token auth
boundary for future protected endpoints, but no protected endpoint is wired.
The local API package still does not execute providers, call RuntimeComposition,
call Core assistant helpers, call AssistantRuntime provider-stage behavior,
store traces, or manage sessions.

Endpoint class: protected endpoint. Requires
`Authorization: Bearer <local-token>`.

Options considered:

- Provider-foundation `TurnInput` -> `TurnOutput`: rejected for the public
  assistant-turn endpoint. Those contracts remain provider-foundation scoped and
  must not be silently repurposed as assistant-turn contracts.
- Direct `AssistantTurnInput` -> `AssistantTurnResult`: accepted as the nested
  contract family for the first endpoint because these are the approved
  assistant-envelope contracts.
- Text-only local API convenience request: rejected for the first
  implementation because it would move input normalization into the HTTP adapter
  or require the API package to import AssistantRuntime helpers.
- API calls RuntimeComposition directly: rejected for `packages.local_api`.
  RuntimeComposition owns execution composition, but the local API package owns
  only HTTP parsing, auth, and serialization.
- API calls Core or AssistantRuntime directly: rejected. Core owns orchestration
  helpers and AssistantRuntime owns provider-stage behavior; neither dependency
  belongs in the HTTP adapter.
- Both fake provider and LM Studio modes in the first endpoint: rejected.
  LM Studio is real-provider proof behavior and must remain explicit CLI/manual
  smoke only until a later service/API promotion task.

Implemented first shape:

- `packages.local_api` owns the HTTP route, bearer auth enforcement, JSON body
  parsing, request validation, and response serialization.
- The endpoint accepts an explicitly injected turn handler. The handler is a
  callable/protocol boundary, not a global singleton and not a local API-owned
  provider/runtime implementation.
- RuntimeComposition remains the owner of future provider/Core/AssistantRuntime
  composition behind that handler. `packages.local_api` must not import
  RuntimeComposition.
- The first concrete provider mode is fake-provider only by request-envelope
  mode. The API does not execute the provider; tests use stubbed handlers only.
- LM Studio Responses over `/v1/turns` remains blocked until a later task
  approves service/API promotion criteria, live-smoke expectations, failure
  policy, and explicit opt-in configuration.

Request body decision:

The first `/v1/turns` request body is a local HTTP adapter envelope that carries
the approved `AssistantTurnInput` contract. It is not a new Core contract and
does not modify `AssistantTurnInput`.

```json
{
  "schema_version": "0.1.1-draft",
  "execution_mode": "assistant_runtime_fake_provider",
  "assistant_turn_input": {
    "schema_version": "0.1.1-draft",
    "trace_id": "trace-001",
    "turn_id": "turn-001",
    "input_event_id": "event-001",
    "session_ref": null,
    "identity_ref": null,
    "user_visible_input": "Hello",
    "assistant_mode": "default",
    "policy_context": {
      "requested_capabilities": [],
      "sensitivity": "normal"
    },
    "metadata": {}
  },
  "model": "fake-model",
  "instructions": null,
  "previous_response_id": null,
  "provider_options": {}
}
```

Request rules:

- `schema_version` is required and must be `0.1.1-draft` for the first
  implementation.
- `execution_mode` is required and the only accepted first value is
  `assistant_runtime_fake_provider`.
- `assistant_turn_input` is required and must validate as `AssistantTurnInput`.
- `assistant_turn_input.trace_id` and `assistant_turn_input.turn_id` are the
  endpoint trace and turn identities.
- `model` is required and non-empty. The local API must pass it through; it must
  not choose models or implement model-selection policy.
- `instructions` is required and nullable.
- `previous_response_id` is required and nullable. When present, it is passed as
  an explicit provider-continuity value to the injected handler. It must not be
  read from `metadata`, stored in hidden state, or treated as session history.
- `provider_options` is required and must be `{}` for the first fake-provider
  implementation unless a later task approves specific keys.
- Unknown top-level fields are rejected with `VALIDATION_ERROR`.
- Request metadata must not carry provider request bodies, provider responses,
  raw prompts, session/history bodies, tool data, memory data, auth material, or
  trace payloads.

Response body decision:

Successful handler completion returns `AssistantTurnResult`.

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "turn_id": "turn-001",
  "assistant_final_response": {
    "schema_version": "0.1.1-draft",
    "response_type": "text",
    "text": "Hello.",
    "payload_ref": null,
    "output_channel_intent": "default",
    "safe_for_display": true,
    "safe_for_speech": true,
    "memory_write_candidate_hint": false,
    "finish_reason": "stop",
    "metadata": {}
  },
  "output_events": [],
  "stage_summaries": [],
  "provider_turn_refs": [
    {
      "ref_type": "provider_turn",
      "ref_id": "fake-response-001",
      "stage_name": "provider_reasoning",
      "provider_name": "fake",
      "status": "completed",
      "trace_id": "trace-001"
    }
  ],
  "tool_result_refs": [],
  "memory_result_refs": [],
  "session_result_ref": null,
  "error": null,
  "metadata": {}
}
```

Response rules:

- `trace_id` and `turn_id` are surfaced only through the returned
  `AssistantTurnResult`.
- There is no top-level `provider_response_id` in the HTTP response.
- Provider response identity is exposed only as a reference/summary in
  `provider_turn_refs[].ref_id`, following the assistant-envelope contract.
- Raw `ProviderRequest`, raw `ProviderResponse`, provider payloads, prompts,
  provider SDK errors, provider options, and trace event bodies must not be
  embedded.
- A completed assistant turn that contains a mapped provider-stage failure still
  returns `AssistantTurnResult` with its nested `error`. Transport/request
  failures return top-level `ErrorEnvelope`.

Auth enforcement decision:

- Auth is checked before body validation or handler invocation.
- Missing, malformed, unconfigured, or wrong bearer tokens return HTTP `401`
  with `ErrorEnvelope.code` `AUTH_REQUIRED`.
- Auth failures use a server-generated local trace id such as
  `trace-local-api-auth-required` unless a later service-runtime task approves a
  per-request trace allocator.
- Token material must not be logged, echoed, persisted, stored in response
  details, or copied into metadata.
- `/health` and `/version` remain public local readiness endpoints and must not
  require auth.

Dependency direction:

```text
HTTP client
  -> packages.local_api protected endpoint adapter
    -> injected turn handler callable/protocol
      -> RuntimeComposition-owned fake-provider bridge
        -> Core assistant-provider-stage helper
          -> AssistantRuntime provider-stage helper
        -> ProviderRuntime fake provider construction
```

Allowed imports for `packages.local_api` in the first endpoint implementation:

- approved contract models and enums from `packages.contracts`
- `packages.process_runtime` for existing health/version readiness
- local API modules, including the auth helper
- Python standard-library modules needed for WSGI, JSON parsing, dataclasses,
  typing/protocols, and safe comparisons

Forbidden imports for `packages.local_api`:

- `packages.runtime_composition`
- `packages.core`
- `packages.assistant_runtime`
- `packages.provider_runtime`
- `packages.adapters`
- `packages.telemetry` implementation modules
- `apps`
- `services`
- provider SDKs

Forbidden first-endpoint behavior:

- no direct RuntimeComposition/Core/AssistantRuntime/ProviderRuntime calls from
  `packages.local_api`
- no LM Studio or other real-provider API execution
- no provider routing, retry/fallback, model-selection policy, API-key policy,
  preflight probing, sessions, history, trace API, WebSocket, service daemon,
  supervisor lifecycle, tools, memory, UI, voice, desktop, vision, proactive
  behavior, or long-running tasks
- no hidden global handler, token, session, or trace state
- no default CLI behavior change

Error behavior:

- Missing or invalid auth: HTTP `401`, top-level `ErrorEnvelope` with
  `AUTH_REQUIRED`.
- Unknown route: HTTP `404`, top-level `ErrorEnvelope` with `NOT_FOUND`.
- Malformed JSON, non-object JSON, missing required fields, invalid
  `AssistantTurnInput`, unsupported `execution_mode`, non-empty
  `provider_options`, or unknown top-level fields: HTTP `400`, top-level
  `ErrorEnvelope` with `VALIDATION_ERROR`.
- Handler not configured or explicitly unavailable: HTTP `503`, top-level
  `ErrorEnvelope` with `SERVICE_UNHEALTHY`.
- Unexpected implementation exception: HTTP `500`, top-level `ErrorEnvelope`
  with `INTERNAL_ERROR` and no raw exception detail.
- Provider-stage failures returned by the handler remain nested inside
  `AssistantTurnResult.error` when the handler completed and returned a valid
  assistant result.

Trace/provider reference exposure:

- `/v1/turns` returns only the assistant result shape.
- Trace events remain unavailable over HTTP until a separate trace API task.
- Provider references are summaries only through `provider_turn_refs`.
- Provider response ids must not become a top-level assistant-turn result field.

What remains blocked:

- real-provider `/v1/turns` execution
- LM Studio API endpoint mode
- trace retrieval or event streaming
- local service daemon or lifecycle management
- token generation, discovery, rotation, or persistence
- session/history state
- routing, retry/fallback, model-selection, API-key policy, tools, memory, UI,
  voice, desktop, vision, proactive behavior, and product runtime behavior

Current implementation note:

Task 121 implements the protected fake-provider-only `/v1/turns` adapter with
an injected handler shape:
`Callable[[LocalTurnRequestEnvelope], AssistantTurnResult]`. Auth is enforced
before body parsing or handler invocation. The local API package still does not
import or call RuntimeComposition, Core, AssistantRuntime, ProviderRuntime,
provider adapters, CLI apps, services, telemetry implementation modules, or
provider SDKs.

Next task unlocked:

Decide whether and how a separate composition owner may provide the injected
handler for local fake-provider smoke. That future task must not add real
provider API mode, LM Studio API mode, trace API, WebSocket, service daemon
behavior, sessions/history, routing, retry/fallback, model-selection, API-key
policy, tools, memory, UI, voice, desktop, vision, or default CLI changes
unless explicitly approved.

Rollback path:

If this contract proves too narrow, revert the `/v1/turns` endpoint to the
existing unknown-route `NOT_FOUND` behavior and remove any injected handler
wiring. Because execution stays outside `packages.local_api`, rollback should
not require changes to Core, AssistantRuntime, ProviderRuntime, provider
adapters, RuntimeComposition bridge internals, or default CLI behavior.

### GET /v1/traces/{trace_id}

Future protected endpoint. Requires `Authorization: Bearer <local-token>`.

Returns trace events for one turn.

Requires local auth. Must return only the requested trace for the current local session unless a future approved session store changes that rule.

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

## IPC Rules

- Every request carries `trace_id`.
- Every response declares schema version.
- Every future service exposes health and version.
- No service may return unstructured exceptions.
- No module may depend on in-process calls if it is defined as process-ready.
