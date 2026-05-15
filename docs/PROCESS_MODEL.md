# Process Model

## V1 Process Map

V1 runs as two practical processes:

- CLI Client
- Python Core Service

The Core Service loads a provider adapter through an interface. The fake provider and LM Studio Responses provider are implementation choices behind that interface.

## Future Process Map

The future desktop app should feel like one app while internally behaving like a process-ready system:

- Marvex Shell
- Marvex Core
- Marvex Provider Worker
- Marvex Tool Worker
- Marvex Intent Worker
- Marvex Voice Worker
- Marvex Desktop Agent

## Subprocess Expectations

Every subprocess must expose:

- health check
- version information
- startup protocol
- shutdown protocol
- structured logs
- trace_id propagation
- JSON error envelope

`HealthCheck` and `VersionInfo` contracts exist now for future process
readiness. Task 020 adds a local in-memory object provider for these contracts.
Task 026 plans future HTTP endpoint contracts for those objects. Neither task
adds a subprocess runtime, process supervisor, daemon, HTTP server, service
runtime, socket listener, or network behavior.

Task 117 adds a local health/version WSGI app object for `GET /health` and
`GET /version` only. The default local API config host is `127.0.0.1`. It does
not start a service, bind a socket, supervise subprocesses, call providers, run
assistant turns, implement `/v1/turns`, or add WebSocket/session/history
behavior.

Task 118 adds a manual developer-only runner for that app object. It binds to
`127.0.0.1:8765` by default and is used only for local smoke verification. It is
not a daemon, subprocess supervisor, auto-restart loop, product service mode,
assistant-turn endpoint, provider execution path, or service lifecycle system.

Task 119 defines the local API auth boundary before protected endpoint work.
Health/version readiness endpoints remain public on loopback. Future turn,
trace, and event endpoints must require `Authorization: Bearer <local-token>`.
Token creation, discovery, rotation, persistence, and service lifecycle wiring
remain future service-runtime work.

Task 120 decides the future protected `POST /v1/turns` contract before endpoint
implementation. The first implementation target is fake-provider only through
an injected turn handler. The local API package remains the HTTP/auth/JSON
adapter and must not call RuntimeComposition, Core, AssistantRuntime,
ProviderRuntime, provider adapters, or provider SDKs directly. LM Studio
Responses API mode, trace retrieval, event streaming, service daemon lifecycle,
sessions/history, routing, retry/fallback, model selection, API-key policy,
tools, memory, UI, voice, desktop, vision, and proactive behavior remain future
explicit tasks.

Task 121 implements that protected `/v1/turns` HTTP/auth/JSON adapter with an
injected handler. The endpoint validates the Task 120 local request envelope and
serializes `AssistantTurnResult`, but it still does not provide the execution
composition behind the handler.

Task 122 adds the first fake-provider execution handler factory in
RuntimeComposition. The handler can be injected into the local API app and uses
the existing fake-provider bridge path. The local API package still owns only
HTTP/auth/JSON behavior, and the manual runner remains health/version-only.

Task 123 adds a developer-only fake-turns smoke runner in RuntimeComposition.
It injects the fake handler into the local API runner with a caller-provided
fake/dev bearer token. The local API package remains a generic runner and app
adapter; it still does not import RuntimeComposition.

Task 126 decides that a future trace endpoint should exist before real-provider
local API turn execution, but only as protected current-process trace reading.
The first trace store/read model should be telemetry-owned, in-memory, injected
explicitly into local service composition, and cleared on process exit. Local
API may expose it only as an auth/JSON adapter; RuntimeComposition must not own
trace lookup or storage.

## Failure Rule

A non-critical subprocess failure must not corrupt Core state. The Shell may crash without killing Core. Provider Worker failure must return an error envelope, not crash the turn lifecycle. Future workers must degrade cleanly.

## Startup Order

Future process mode:

1. CLI starts or connects to Core Service.
2. Core Service reports health and version.
3. CLI submits a turn.
4. Core calls provider through the provider port.
5. Core emits trace events.
6. CLI receives final response.

Future:

1. Shell starts.
2. Shell supervises or discovers Core.
3. Core discovers configured workers.
4. Each worker reports health and version.
5. Shell and Core exchange events over localhost APIs.

Current Provider Foundation runtime is still in-process/CLI driven. Current
ProcessRuntime remains local-only object construction from explicit in-memory
config. Health/version local API readiness now includes an app object and a
manual loopback runner only. Auth-token policy exists for future protected
endpoints and protects the `/v1/turns` adapter. Task 120 narrows `/v1/turns` to
protected fake-provider only with an injected handler. Task 121 implements only
that protected adapter. Task 122 adds fake-provider handler composition outside
local API. Task 123 adds manual fake-turns smoke composition in
RuntimeComposition. Task 126 decides trace exposure ownership and safety but
does not implement a trace API or trace storage. WebSocket, service lifecycle,
subprocess supervision, persistence, and real-provider API execution remain
future explicit service-runtime work.
