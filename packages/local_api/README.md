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

Task 120 `/v1/turns` decision:

- Future `POST /v1/turns` is protected and must use the local bearer-token auth
  policy before body validation or handler invocation.
- The first implementation target is fake-provider only through an injected turn
  handler. The local API package owns HTTP parsing, auth, validation, and
  serialization only.
- The request body is a local HTTP adapter envelope carrying an approved
  `AssistantTurnInput`, plus explicit `execution_mode:
  "assistant_runtime_fake_provider"`, `model`, nullable `instructions`,
  nullable `previous_response_id`, and empty `provider_options`.
- The response body is `AssistantTurnResult` when the handler completes.
  Request/auth/transport failures return top-level `ErrorEnvelope`.
- `trace_id` and `turn_id` are surfaced through `AssistantTurnResult`.
  Provider identity is exposed only through `provider_turn_refs`; there is no
  top-level `provider_response_id`.
- `previous_response_id` is explicit request-envelope input only. It must not be
  read from metadata, stored as session/history state, or made implicit.
- RuntimeComposition remains the owner of future provider/Core/AssistantRuntime
  composition behind the injected handler. This package must not import
  RuntimeComposition, Core, AssistantRuntime, ProviderRuntime, adapters,
  telemetry implementation modules, CLI apps, services, or provider SDKs.

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
