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

## Failure Rule

A non-critical subprocess failure must not corrupt Core state. The Shell may crash without killing Core. Provider Worker failure must return an error envelope, not crash the turn lifecycle. Future workers must degrade cleanly.

## Startup Order

V1:

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

