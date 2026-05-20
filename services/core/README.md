# Core Service

Status: approved contract, documentation-only service surface, no entrypoint or runtime code yet.

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

## Next Implementation Prerequisites

Before code, this surface needs lifecycle contract docs, envelope/schema tests, and validation gates that prove the service boundary can start, report readiness, fail safely, and shut down cleanly.
