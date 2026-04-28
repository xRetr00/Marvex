# IPC API

Marvex will use localhost HTTP, WebSocket, and JSON communication between the app shell and services in a future process/runtime phase.

Provider Foundation currently has JSON contracts and a local in-memory
health/version object provider only. Task 020 does not implement HTTP servers,
endpoints, subprocesses, daemons, or networking.

Task 026 defines future endpoint contracts only. It does not implement an HTTP
server, service daemon, subprocess runtime, socket listener, framework
dependency, or service mode.

No HTTP implementation exists in Task 026.

## Localhost Security Defaults

- Services must bind to `127.0.0.1` by default.
- Binding to `0.0.0.0`, LAN addresses, or remote interfaces is forbidden unless a future remote mode is explicitly approved.
- Future remote mode must be explicit opt-in, documented by RFC, and covered by authentication, authorization, transport security, and threat-model review.
- The future server must require a random local auth token generated at startup or a clearly marked dev token for local development.
- Auth token requirements in this document are contract-level only; generation,
  storage, rotation, and validation mechanics are future implementation details.
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

These endpoint contracts are localhost-only by default. They define wire
behavior for a future service-runtime task without selecting a Python HTTP
framework or authorizing runtime implementation.

HTTP status mapping:

- `200`: success response body.
- `4xx`: auth, client, or request/contract error response body.
- `5xx`: service or internal error response body.

All error response bodies must use `ErrorEnvelope`.

### GET /health

Future localhost-only endpoint.

Request body: none.

Success: `200` with `HealthCheck`.

Error: `4xx` or `5xx` with `ErrorEnvelope`.

Missing or invalid auth maps to `AUTH_REQUIRED` inside `ErrorEnvelope`.

`HealthCheck` currently has no timestamp field. `uptime_seconds` is future
runtime uptime in non-negative seconds. `dependencies` is a JSON object only;
there is no approved nested dependency-status schema yet. The endpoint must not
probe providers or dependencies until a future dependency-status contract is
approved.

### GET /version

Future localhost-only endpoint.

Request body: none.

Success: `200` with `VersionInfo`.

Error: `4xx` or `5xx` with `ErrorEnvelope`.

Missing or invalid auth maps to `AUTH_REQUIRED` inside `ErrorEnvelope`.

`VersionInfo` currently has no timestamp field. `contract_versions` and `build`
are JSON objects; detailed build metadata shape is future contract work.

### POST /v1/turns

Accepts `TurnInput`.

Returns `TurnOutput`.

### GET /v1/traces/{trace_id}

Returns trace events for one turn.

Requires local auth. Must return only the requested trace for the current local session unless a future approved session store changes that rule.

### WS /v1/events

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
