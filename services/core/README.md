# Core Service

Status: approved minimal local Core service entrypoint.

`packages/core/service.py` is the pure Core orchestration foundation:
lifecycle, health/version, turn submission through a port, and structured
`ErrorEnvelope` behavior. It remains transport-free.

`services/core/main.py` is the runnable service-owned entrypoint: CLI parsing,
loopback Local API startup, provider selection flags, safe startup metadata,
health/version one-shot, ProviderWorker process roundtrip proof, and shutdown
wiring.

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

The current closure slice is intentionally local-only and minimal:

- CoreService can start, report health/version, submit assistant turns through
  an injected executor port, and shut down.
- It uses approved `HealthCheck`, `VersionInfo`, `AssistantTurnInput`,
  `AssistantTurnResult`, and `ErrorEnvelope` contracts.
- `services/core/main.py` composes CoreService behind the existing Local API
  without adding Local API imports to `packages/core`.
- Startup binds to `127.0.0.1` by default. Remote bind and `0.0.0.0` modes are
  not approved.
- Failures at the CoreService envelope return structured `ErrorEnvelope`
  results instead of leaking raw exceptions.
- The default turn path remains fake-provider CI/dev safe.
- Core can select the local ProviderWorker process boundary and send an
  assistant turn through ProviderWorker -> ProviderRuntime -> FakeProvider.
- LM Studio Responses and LiteLLM provider flags are entrypoint configuration
  for the provider boundary and do not add concrete provider imports to
  `packages/core`.

Runnable commands:

```powershell
uv run python -m services.core.main --help
uv run python -m services.core.main --health-once
uv run python -m services.core.main --serve --local-auth-token <local-token>
uv run python -m services.core.main --turn-once "hello" --provider provider_worker --model fake-model
```

Future production daemon supervision, external process managers, streaming
worker IPC, remote bind modes, raw prompt/provider-output persistence, hidden
autostart, and full assistant OS worker orchestration still require separate
approved tasks.
