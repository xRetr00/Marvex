# Core Service

Status: approved contract with in-process CoreService lifecycle envelope in
`packages/core/service.py`. No service-owned process entrypoint exists under
`services/core` yet.

## Intended Ownership

CoreService owns assistant lifecycle coordination and worker orchestration only. It is the process boundary that starts the assistant session, coordinates worker requests, tracks turn state, and publishes process-level events through approved contracts.

## Lifecycle Expectations

The service must define explicit start, readiness, health, version, and shutdown behavior before code exists.

- Start: boot as a bounded service process with declared dependencies and schema version awareness.
- Readiness: report ready only after orchestration state is initialized and required worker endpoints or adapters are available.
- Health/version: expose health and version information that reflects process state, contract schema version, and degraded conditions.
- Shutdown: stop accepting new work, drain or cancel in-flight orchestration, and emit a clean terminal event.
- Degraded failure behavior: fail closed on missing required worker dependencies, surface explicit error envelopes, and keep partial state isolated from caller assumptions.

## IPC And Envelope Expectation

All service interaction must use JSON-compatible command, request, result, event, and error envelopes.

- `trace_id` must propagate across all requests, events, and errors.
- `schema_version` must be present on every envelope family used by the service.
- Error responses must use the approved error envelope shape rather than ad hoc strings or exceptions.

## High-Level Dependencies

CoreService may depend on worker ports, lifecycle adapters, telemetry/event plumbing, and contract-validated state projection. It may coordinate provider, intent, tool, memory, voice, desktop, and policy boundaries only through ports and approved envelopes.

## Explicit Exclusions

CoreService must never own provider protocols, tool execution, memory storage, UI, voice, desktop automation, policy approval, provider routing, or session storage. It must not become the provider router, model-policy engine, tool runner, or conversation database.

## Implemented Closure Slice

The current closure slice is intentionally in-process and orchestration-only:

- CoreService can start, report health/version, submit assistant turns through
  an injected executor port, and shut down.
- It uses approved `HealthCheck`, `VersionInfo`, `AssistantTurnInput`,
  `AssistantTurnResult`, and `ErrorEnvelope` contracts.
- It can be composed behind the existing Local API from outside Core, but Core
  does not import Local API or own HTTP exposure.
- Failures at the CoreService envelope return structured `ErrorEnvelope`
  results instead of leaking raw exceptions.

Future process entrypoints, worker IPC, supervision, and daemon behavior still
require separate approved tasks.
