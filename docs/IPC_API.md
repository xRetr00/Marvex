# IPC API

Marvex uses localhost HTTP, WebSocket, and JSON communication between the app shell and services.

V1 uses plain JSON over HTTP for request-response flows and WebSocket for event streams.

## V1 HTTP Endpoints

### GET /health

Returns `HealthCheck`.

### GET /version

Returns `VersionInfo`.

### POST /v1/turns

Accepts `TurnInput`.

Returns `TurnOutput`.

### GET /v1/traces/{trace_id}

Returns trace events for one turn.

### WS /v1/events

Streams `TraceEvent` records and later service lifecycle events.

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
- Every service exposes health and version.
- No service may return unstructured exceptions.
- No module may depend on in-process calls if it is defined as process-ready.

