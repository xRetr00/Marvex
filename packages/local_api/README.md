# Local API Package

Status: local health/version API readiness foundation.

Ownership: local API adapter boundary for approved process-readiness contracts.

Current behavior:

- `create_health_version_api_app(...)` creates a dependency-free WSGI app object.
- `python -m packages.local_api.runner` starts a manual developer-only runner
  for that app object.
- `GET /health` returns the existing `HealthCheck` contract shape.
- `GET /version` returns the existing `VersionInfo` contract shape.
- Unknown routes return a safe `ErrorEnvelope` with `NOT_FOUND`.
- `LocalApiConfig` defaults to `host="127.0.0.1"` and `port=8765`.
- `validate_local_bearer_token(...)` provides a reusable local auth-token
  check for future protected endpoints. It is not wired to `/health` or
  `/version`.

Endpoint classes:

- Public local readiness endpoints: `GET /health` and `GET /version`.
- Protected future endpoints: assistant turn submission, trace access, and
  event streams.

Auth decision:

- Protected future endpoints must use `Authorization: Bearer <local-token>`.
- Token source is future local service configuration or startup generation.
  Automatic generation and discovery are deferred.
- Explicit development tokens are allowed only when clearly fake and opt-in.
- Missing, malformed, unconfigured, or wrong tokens map to a safe
  `ErrorEnvelope` with `AUTH_REQUIRED`.
- Token values must not be logged, echoed, persisted, or included in error
  details.

Non-behavior:

- No daemon, subprocess supervisor, WebSocket, trace API, or service lifecycle
  runner is added.
- The manual runner is developer smoke only and is not CI or product behavior.
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
