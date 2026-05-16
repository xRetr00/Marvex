# Validation Scripts

These scripts are governance tooling, not Marvex product implementation.

Run all checks from the Marvex root:

```powershell
python scripts/run_all_checks.py
```

Scripts:

- `check_workspace_policy.py`
- `check_docs_accepted.py`
- `check_service_placeholders.py`
- `check_forbidden_modules.py`
- `check_task_spec.py`
- `check_agent_context_budget.py`
- `check_library_decisions.py`
- `check_schema_versions.py`
- `check_project_status.py`
- `check_file_size_policy.py`
- `check_port_boundaries.py`
- `check_provider_runtime_boundaries.py`
- `check_runtime_composition_boundaries.py`
- `check_local_api_boundaries.py`
- `check_local_api_client_boundaries.py`
- `check_local_service_startup_boundaries.py`
- `check_assistant_runtime_boundaries.py`
- `check_provider_structured_output_boundaries.py`
- `check_telemetry_boundaries.py`
- `check_process_runtime_boundaries.py`
- `check_vaxil_boundary.py`

`check_provider_runtime_boundaries.py` enforces the Core, CLI, ProviderPort,
and ProviderRuntime dependency boundary so provider selection stays inside
ProviderRuntime.

`check_runtime_composition_boundaries.py` enforces the RuntimeComposition bridge
boundary so the bridge can compose ProviderRuntime and the Core
assistant-provider-stage helper without importing adapters, AssistantRuntime,
ports, CLI apps, services, or owning routing/session/history/retry/model/API-key
policy. It also limits CLI to the approved RuntimeComposition package-root
bridge functions, including the explicit LM Studio Responses AssistantRuntime
proof mode, and blocks direct CLI ProviderRuntime or adapter imports. The only
approved real-provider identifier in RuntimeComposition source is
`lmstudio_responses`. It has one narrow manual-smoke exception:
`packages/runtime_composition/local_api_fake_turns_runner.py` may import the
local API runner/config to inject the fake-turn handler for developer-only local
API smoke. That exception does not permit RuntimeComposition to own HTTP
parsing, auth validation, routing, sessions/history, retry/fallback,
model-selection, or API-key policy.

`check_assistant_runtime_boundaries.py` enforces the AssistantRuntime dependency
boundary so assistant-envelope helpers, the no-provider skeleton, approved
provider-stage diagnostics, and assistant-runtime-owned state primitives stay
isolated from Core, Local API, local service startup, RuntimeComposition,
ProviderRuntime, adapters, ports, apps, services, concrete providers, provider
bridge terms, and future subsystem behavior. It also blocks other runtime
owners from directly mentioning AssistantRuntime state primitive names.

`check_provider_structured_output_boundaries.py` enforces the no-network
provider structured-output adapter boundary so validation stays isolated from
Core, AssistantRuntime, ProviderRuntime, adapters, ports, apps, services,
concrete providers, prompt rendering, provider response ids, and deferred
frameworks.

`check_telemetry_boundaries.py` enforces the telemetry boundary so trace safety,
read projections, and local persistence stay inside `packages/telemetry` without
imports from Local API, RuntimeComposition, Core, ProviderRuntime, adapters,
CLI apps, services, or future subsystem behavior.

`check_process_runtime_boundaries.py` enforces the ProcessRuntime dependency
boundary so local health/version object construction stays isolated until an
explicit future integration task. Strict forbidden behavior token scans apply
only to Python source files under `packages/process_runtime/`, not README or
documentation files.

`check_local_api_boundaries.py` enforces the local API boundary so
`packages/local_api` stays limited to approved `HealthCheck` and `VersionInfo`
response exposure, the protected fake-provider `/v1/turns` HTTP/auth/JSON
adapter, the manual standard-library runner, and local bearer-token auth. It
blocks provider execution, RuntimeComposition, Core assistant execution,
AssistantRuntime provider-stage calls, WebSocket, session/history, routing,
retry/fallback, model/API-key policy, remote-bind defaults, hard-coded
token/secret values, token printing, and service placeholder implementation
drift.

`check_local_api_client_boundaries.py` enforces the narrow future Shell/CLI
client-helper boundary so `packages/local_api_client` can read safe discovery
metadata and make explicit JSON calls without becoming a daemon, token store,
RuntimeComposition owner, provider router, retry/session layer, or product UI.

`check_local_service_startup_boundaries.py` enforces the local service startup
foundation boundary so startup metadata and local bearer-token generation stay
outside Core, ProviderRuntime, Local API handlers, and RuntimeComposition. It
allows only the approved safe discovery writer path, and otherwise blocks
environment reads, framework imports, provider execution, WebSocket behavior,
and provider bridge calls in the startup package.

`check_library_decisions.py` enforces required decision fields and confirms each
runtime dependency in `[project].dependencies` has a matching decision record.

`check_schema_versions.py` enforces the active Provider Foundation schema
version policy from `docs/SCHEMA_VERSION_POLICY.md`.

`check_project_status.py` prevents stale project status after major governance
milestones.

`check_agent_context_budget.py` keeps the agent context architecture docs
discoverable and verifies the task-spec Context Pack fields remain present. It
uses targeted phrase and field checks only; it does not inspect shell history or
attempt to enforce actual agent tool usage.

Manual smoke scripts:

- `smoke_providers.py`
- `spike_lmstudio_structured_output.py`

`smoke_providers.py` is developer-only manual verification for provider paths.
It is intentionally excluded from `run_all_checks.py` and must not become a CI
dependency.

`spike_lmstudio_structured_output.py` is developer-only manual observation for
LM Studio Responses provider-native structured-output compatibility. It is
intentionally excluded from `run_all_checks.py` and must not become a CI
dependency.
