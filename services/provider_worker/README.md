# Provider Worker

Status: approved contract, documentation-only service surface, no entrypoint or runtime code yet.

## Intended Ownership

ProviderWorker owns provider request execution behind `ProviderPort`, `ProviderRuntime`, and adapter boundaries. It is the execution boundary for turning a validated provider request into a provider response.

## Lifecycle Expectations

The service must define explicit start, readiness, health, version, and shutdown behavior before code exists.

- Start: initialize provider adapters and declared runtime dependencies only.
- Readiness: report ready only when the selected provider runtime and adapter set are initialized.
- Health/version: expose health and version information for process state, runtime availability, and contract schema version.
- Shutdown: stop accepting requests, let in-flight provider calls finish or fail explicitly, and then exit cleanly.
- Degraded failure behavior: surface provider failures through approved error envelopes and stay isolated from retry, fallback, or routing decisions that belong elsewhere.

## IPC And Envelope Expectation

All service interaction must use JSON-compatible command, request, result, event, and error envelopes.

- `trace_id` must propagate across all requests, events, and errors.
- `schema_version` must be present on every envelope family used by the service.
- Error responses must use the approved error envelope shape rather than ad hoc strings or exceptions.

## High-Level Dependencies

ProviderWorker may depend on provider SDKs, model adapters, transport adapters, telemetry, and contract-validated request/result mapping. It may call only provider-facing runtime and adapter ports.

## Explicit Exclusions

ProviderWorker must never own routing, model policy, fallback selection, session storage, tools, memory, prompt assembly, or orchestration logic. It must not decide which provider to use or how assistant state progresses.

## Next Implementation Prerequisites

Before code, this surface needs lifecycle contract docs, envelope/schema tests, adapter boundary tests, and validation gates that prove provider execution stays isolated behind `ProviderPort` and `ProviderRuntime`.
