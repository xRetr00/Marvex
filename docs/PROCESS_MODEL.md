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
config. HTTP exposure remains future explicit service-runtime work and must not
be inferred from the presence of health/version contracts or endpoint planning.
