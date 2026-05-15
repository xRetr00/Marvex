# Local API Package

Status: local health/version API readiness plus protected fake-turn adapter.

Ownership: local API adapter boundary for approved process-readiness and
assistant-envelope contracts.

Current behavior:

- `create_health_version_api_app(...)` creates a dependency-free WSGI app object.
- `python -m packages.local_api.runner` starts a manual developer-only runner
  for that app object.
- `GET /health` returns the existing `HealthCheck` contract shape.
- `GET /version` returns the existing `VersionInfo` contract shape.
- `POST /v1/turns` is protected by local bearer auth and accepts only the
  Task 120 fake-provider request envelope through an injected handler.
- Unknown routes return a safe `ErrorEnvelope` with `NOT_FOUND`.
- `LocalApiConfig` defaults to `host="127.0.0.1"` and `port=8765`.
- `validate_local_bearer_token(...)` enforces auth for `/v1/turns`. It is not
  wired to `/health` or `/version`.

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

Task 121 `/v1/turns` implementation:

- `create_health_version_api_app(...)` accepts optional `turn_handler` and
  `local_auth_token` arguments.
- `turn_handler` has shape
  `Callable[[LocalTurnRequestEnvelope], AssistantTurnResult]`.
- `LocalTurnRequestEnvelope` contains `schema_version`, `execution_mode`,
  `assistant_turn_input`, `model`, nullable `instructions`, nullable
  `previous_response_id`, and empty `provider_options`.
- Auth is enforced before reading or validating the request body and before
  invoking the handler.
- Successful handler results serialize as `AssistantTurnResult` JSON.
- Missing/invalid auth, invalid JSON, invalid request shape, unavailable
  handler, and handler exceptions return safe `ErrorEnvelope` JSON without token
  values or raw exception details.
- Tests use stubbed handlers only. No RuntimeComposition, Core,
  AssistantRuntime, ProviderRuntime, adapter, or provider SDK execution is
  wired into the API.

Task 122 fake handler composition:

- RuntimeComposition now provides `create_local_api_fake_turn_handler(...)` as a
  fake-provider-only handler factory outside this package.
- The local API app can receive that handler through the existing
  `turn_handler` injection argument.
- This package still does not import RuntimeComposition, Core,
  AssistantRuntime, ProviderRuntime, adapters, telemetry implementation modules,
  CLI apps, services, or provider SDKs.
- The manual runner remains health/version-only and does not set a development
  bearer token or inject the fake handler by default.

Task 123 manual smoke support:

- `run_local_health_version_api(...)` accepts an injected `turn_handler` and
  `local_auth_token` for manual composition by another package.
- The RuntimeComposition-owned fake-turns smoke runner uses that injection path.
- This package still does not import RuntimeComposition or decide execution
  policy.

Task 126 trace exposure decision:

- Future `GET /v1/traces/{trace_id}` must be protected by the same local bearer
  auth policy as `/v1/turns`.
- The first implementation may receive an injected trace reader and serialize a
  safe local API envelope only.
- This package must not own trace storage, sanitizer policy, persistence,
  RuntimeComposition calls, Core calls, AssistantRuntime calls, ProviderRuntime
  calls, or provider execution.

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
- No trace storage or trace endpoint behavior is implemented.
- The manual runner is developer smoke only and is not CI or product behavior.
- No real execution composition is implemented behind `/v1/turns`.
- No provider, RuntimeComposition, Core assistant turn, or AssistantRuntime
  provider-stage execution is invoked by this package.
- No sessions, history, routing, retry/fallback, model selection, API-key
  policy, tools, memory, UI, voice, desktop, vision, or proactive behavior.
- No new runtime dependency or HTTP framework is added.

Dependency direction:

- May depend on approved contracts and `packages.process_runtime`.
- Must not depend on Core, AssistantRuntime, ProviderRuntime,
  RuntimeComposition, adapters, telemetry implementation, CLI apps, or services.
