# Provider Worker

Status: approved local service boundary with runnable JSONL process entrypoint.

## Intended Ownership

ProviderWorker owns local provider request execution behind `ProviderPort`,
`ProviderRuntime`, provider selection, retry/fallback policy execution, and
adapter boundaries. It is the service-owned worker boundary for turning a
validated provider request into a provider response.

## Lifecycle Expectations

The service must define explicit start, readiness, health, version, and shutdown behavior before code exists.

- Start: initialize process state and accept JSONL commands.
- Readiness: report ready after the worker controller is initialized.
- Health/version: expose health and version information for process state, runtime availability, and contract schema version.
- Shutdown: stop accepting requests, let in-flight provider calls finish or fail explicitly, and then exit cleanly.
- Degraded failure behavior: surface provider failures through approved error envelopes and keep retry/fallback execution inside this worker boundary.

## IPC And Envelope Expectation

All service interaction must use JSON-compatible command, request, result, event, and error envelopes.

- `trace_id` must propagate across all requests, events, and errors.
- `schema_version` must be present on every envelope family used by the service.
- Error responses must use the approved error envelope shape rather than ad hoc strings or exceptions.

Implemented JSONL commands:

- `start`
- `stop`
- `status`
- `health`
- `version`
- `send`

## High-Level Dependencies

ProviderWorker may depend on ProviderRuntime, ProviderSelectionRuntime, provider
SDK adapters behind ProviderRuntime, and contract-validated request/result
mapping. It may call only provider-facing runtime and adapter ports.

## Explicit Exclusions

ProviderWorker must never own session storage, tools, memory, prompt assembly,
assistant orchestration, UI, desktop, voice, or proactive behavior. Provider
selection, availability, retry, fallback, timeout, and structured provider
failure classification are intentionally worker-owned for this local provider
execution slice.

## Runnable Commands

```powershell
uv run python -m services.provider_worker.main --help
uv run python -m services.provider_worker.main --health-once
uv run python -m services.provider_worker.main --version-once
uv run python -m services.provider_worker.main --jsonl
```

The `send` command calls `create_provider(...)` and then
`provider.send(...)`. Fake provider requests work without live network access.
LM Studio Responses and LiteLLM construction plumbing exists for local/manual
use and CI tests use fakes or monkeypatched adapters.

Future work remains: streaming, normalized usage schema, provider tool-call
worker surface, production daemon supervision, and a remote mode RFC.
