# Intent Worker

Status: approved contract, documentation-only service surface, no entrypoint or runtime code yet.

## Intended Ownership

IntentWorker owns intent and goal classification plus safe route projection only. It turns an incoming assistant request into bounded intent signals, candidate routes, and other non-executable projections for downstream coordination.

## Lifecycle Expectations

The service must define explicit start, readiness, health, version, and shutdown behavior before code exists.

- Start: boot as a classifier service with declared schema and model/dependency configuration.
- Readiness: report ready only when classification resources and schema validation are available.
- Health/version: expose health and version information that includes process state and contract schema version.
- Shutdown: stop accepting new classification work, drain in-flight requests, and exit with a clear terminal state.
- Degraded failure behavior: fail closed on ambiguous or invalid inputs, return explicit error envelopes, and avoid inventing execution decisions when confidence is insufficient.

## IPC And Envelope Expectation

All service interaction must use JSON-compatible command, request, result, event, and error envelopes.

- `trace_id` must propagate across all requests, events, and errors.
- `schema_version` must be present on every envelope family used by the service.
- Error responses must use the approved error envelope shape rather than ad hoc strings or exceptions.

## High-Level Dependencies

IntentWorker may depend on classifier models, prompt or feature adapters, telemetry, and contract-validated input/output schemas. It may emit route projections and safe metadata for downstream workers.

## Explicit Exclusions

IntentWorker must never own tool dispatch, memory retrieval, provider calls, policy approval, prompt assembly, or execution planning. It must not become the orchestrator or the source of truth for assistant state.

## Next Implementation Prerequisites

Before code, this surface needs lifecycle contract docs, classification-envelope tests, schema validation gates, and safety tests that prove output remains projection only.
