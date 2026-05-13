# Local API Package

Status: local health/version API readiness foundation.

Ownership: local API adapter boundary for approved process-readiness contracts.

Current behavior:

- `create_health_version_api_app(...)` creates a dependency-free WSGI app object.
- `GET /health` returns the existing `HealthCheck` contract shape.
- `GET /version` returns the existing `VersionInfo` contract shape.
- Unknown routes return a safe `ErrorEnvelope` with `NOT_FOUND`.
- `LocalApiConfig` defaults to `host="127.0.0.1"` and `port=8765`.

Non-behavior:

- No server listener, daemon, subprocess supervisor, WebSocket, trace API, or
  service lifecycle runner is added.
- No `/v1/turns` endpoint is implemented.
- No provider, RuntimeComposition, Core assistant turn, or AssistantRuntime
  provider-stage execution is invoked.
- No sessions, history, routing, retry/fallback, model selection, API-key
  policy, tools, memory, UI, voice, desktop, vision, or proactive behavior.
- No new runtime dependency or HTTP framework is added.

Dependency direction:

- May depend on approved contracts and `packages.process_runtime`.
- Must not depend on Core, AssistantRuntime, ProviderRuntime,
  RuntimeComposition, adapters, telemetry implementation, CLI apps, or services.
