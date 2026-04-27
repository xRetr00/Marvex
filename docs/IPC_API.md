# IPC API

Marvex will use localhost HTTP, WebSocket, and JSON communication between the app shell and services in a future process/runtime phase.

Provider Foundation currently has JSON contracts only. Task 019 formalizes
health and version contracts for process readiness but does not implement HTTP
servers, endpoints, subprocesses, daemons, or networking.

## Localhost Security Defaults

- Services must bind to `127.0.0.1` by default.
- Binding to `0.0.0.0`, LAN addresses, or remote interfaces is forbidden unless a future remote mode is explicitly approved.
- Future remote mode must be explicit opt-in, documented by RFC, and covered by authentication, authorization, transport security, and threat-model review.
- The server must require a random local auth token generated at startup or a clearly marked dev token for local development.
- The auth token must not be logged by default.
- Browser-facing clients must use restrictive CORS and origin checks. Default allowed origins are local app origins only.
- WebSocket clients must authenticate before receiving events.
- Trace data access requires the same local auth token as turn submission.
- Trace endpoints must not expose traces across sessions unless a future explicit session contract allows it.
- Ports must default to configurable local ports. If a preferred port is busy, the service may choose an available local port and report it through startup output or a local discovery file.
- Port selection must not silently expose a service on a remote interface.

## Future HTTP Endpoints

The following endpoints are future explicit tasks. Their response contracts
exist now, but no endpoint implementation exists in Task 019.

### GET /health

Returns `HealthCheck`.

`HealthCheck` currently has no timestamp field. `uptime_seconds` is future
runtime uptime in non-negative seconds. `dependencies` is a JSON object only;
there is no approved nested dependency-status schema yet.

### GET /version

Returns `VersionInfo`.

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
