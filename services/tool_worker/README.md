# Tool Worker

Status: approved contract, documentation-only service surface, no entrypoint or runtime code yet.

## Intended Ownership

ToolWorker owns isolated tool execution only after CapabilityRuntime approval. It executes approved tool actions inside a constrained runtime and returns safe summaries, results, and events.

## Lifecycle Expectations

The service must define explicit start, readiness, health, version, and shutdown behavior before code exists.

- Start: initialize only the sandbox, tool adapters, and approved execution runtime.
- Readiness: report ready only when the sandbox and required tool adapters are available.
- Health/version: expose health and version information for runtime state and contract schema version.
- Shutdown: stop accepting new tool calls, let in-flight executions finish or terminate explicitly, and emit a clean exit signal.
- Degraded failure behavior: fail closed on sandbox, adapter, or approval failures; return explicit error envelopes; and preserve isolation between tool failures and higher-level assistant flow.

## IPC And Envelope Expectation

All service interaction must use JSON-compatible command, request, result, event, and error envelopes.

- `trace_id` must propagate across all requests, events, and errors.
- `schema_version` must be present on every envelope family used by the service.
- Error responses must use the approved error envelope shape rather than ad hoc strings or exceptions.

## High-Level Dependencies

ToolWorker may depend on CapabilityRuntime approval results, sandbox adapters, tool-specific adapters, telemetry, and contract-validated request/result schemas. It may return execution results and safe summaries only.

## Explicit Exclusions

ToolWorker must never own approval logic, arbitrary shell or filesystem backdoors, policy decisions, provider continuation, memory storage, or orchestration of other workers. It must not bypass capability approval or expand into a general-purpose runner.

## Next Implementation Prerequisites

Before code, this surface needs lifecycle contract docs, sandbox/result-envelope tests, approval-gate tests, and validation gates that prove execution remains isolated and approval-driven.
