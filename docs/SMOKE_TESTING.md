# Manual Smoke Testing

Provider smoke testing is developer-only verification. It is not Marvex product
runtime, and it must not become a CI requirement.

The smoke harness is intentionally excluded from `scripts/run_all_checks.py`.
Run it manually from the repository root when you explicitly want to exercise a
provider path:

```powershell
python scripts/smoke_providers.py --provider fake
python scripts/smoke_providers.py --provider lmstudio_responses --model <local-model>
python scripts/smoke_providers.py --provider lmstudio_responses_continuity --model <local-model>
python scripts/smoke_providers.py --provider litellm --model <configured-model>
```

The script prints PASS or FAIL lines, trace ids, provider response ids, and
bounded response previews. It does not store prompts, responses, traces, or
logs. Do not pass secrets as prompt text, model names, or command-line values.

## LM Studio Structured Output Spike

The structured-output spike harness is manual and opt-in only. It observes LM
Studio Responses provider-native structured-output behavior through the pinned
OpenAI Python SDK dependency. It is not part of CI or `run_all_checks.py`.

```powershell
python scripts/spike_lmstudio_structured_output.py --model <local-model>
```

Optional flags:

- `--base-url`, defaulting to `http://localhost:1234/v1`
- `--timeout-seconds`
- `--show-raw-preview`, which prints only a bounded 300-character preview

The harness prints sanitized observation blocks only. It does not persist trace
logs, prompts, full provider outputs, provider secrets, or environment values.

## Fake Provider

The fake smoke target is local and deterministic. It does not require internet
access or LM Studio:

```powershell
python scripts/smoke_providers.py --provider fake
```

## LM Studio Responses

The LM Studio targets are opt-in only. Before running them:

- Start the LM Studio local server.
- Confirm the server exposes the OpenAI-compatible API at
  `http://localhost:1234/v1`.
- Load a local model and pass that model name with `--model`.

Single-turn smoke:

```powershell
python scripts/smoke_providers.py --provider lmstudio_responses --model <local-model>
```

RuntimeComposition real-provider AssistantRuntime proof:

- Task 113 adds a RuntimeComposition proof path for `lmstudio_responses`.
- Automated validation uses stubbed ProviderRuntime behavior and does not require
  a live LM Studio server.
- Task 114 adds an explicit non-default CLI proof mode for that bridge.
- CLI live execution is manual smoke only and is not part of CI or
  `run_all_checks.py`.
- Use the existing provider smoke command above to verify the underlying live
  LM Studio Responses adapter before the CLI bridge smoke.

CLI AssistantRuntime bridge smoke:

```powershell
python apps\cli\main.py --assistant-runtime-lmstudio-responses --text "Hello" --model <local-model>
```

Live smoke checklist:

- LM Studio local server must be running.
- Confirm the server exposes the OpenAI-compatible API at
  `http://localhost:1234/v1`.
- A model must be loaded in LM Studio before invoking the command.
- Pass the loaded model name explicitly with `--model <local-model>`.
- Run the underlying provider smoke first if adapter reachability is unclear:
  `python scripts/smoke_providers.py --provider lmstudio_responses --model <local-model>`.
- This is manual smoke only and is not part of CI or `run_all_checks.py`.

Expected success output:

- first line: bounded assistant response text from the loaded model
- `provider_response_id: ...` when the backend returns a provider response id
- `trace_id: trace-...`
- `turn_id: turn-...`
- process exit code `0`

Expected failure output:

- first line: safe failure message from the existing Core/AssistantRuntime
  provider-stage error mapping
- `error_code: ...`
- `provider_response_id: ...` when a provider reference exists
- `trace_id: trace-...`
- `turn_id: turn-...`
- process exit code `1` for mapped provider-stage failures

Failure policy for the explicit CLI proof mode:

- provider unavailable / connection refused: report `Provider unavailable.`
  with `PROVIDER_UNAVAILABLE` when the existing provider-stage mapping receives
  a connection-like failure.
- model missing or rejected by backend: report the existing sanitized provider
  error message and `PROVIDER_ERROR`; do not add model probing or model
  selection policy in CLI.
- timeout-like failure: report `Provider request timed out.` with
  `PROVIDER_TIMEOUT` when the existing provider-stage mapping receives a
  timeout-like failure.
- provider error response: report the sanitized provider error message and
  `PROVIDER_ERROR`.
- empty output: report `Provider output was empty.` with `VALIDATION_ERROR`.
- malformed provider response: report a safe validation/provider-stage error
  message without raw provider payloads or exception details.

This proof mode does not add automatic preflight probing, retry/fallback,
routing, sessions/history, model-selection policy, API-key policy, telemetry
storage, service/API behavior, or product default behavior.

Latest manual execution record:

- Date: 2026-05-13.
- Command shape:
  `python apps\cli\main.py --assistant-runtime-lmstudio-responses --text "Hello" --model <local-model>`.
- Model used: `qwen3.5-0.8b`.
- Environment: LM Studio local server responded at `http://localhost:1234/v1`;
  the model list included `qwen3.5-0.8b`.
- Result: success, exit code `0`.
- Observed assistant response text: yes; bounded excerpt:
  `Hello! How can I help you today? ?`
- Observed `provider_response_id`: yes.
- Observed `trace_id`: yes.
- Observed `turn_id`: yes.
- Note: the first run exposed a Windows legacy-console Unicode print failure
  when the provider returned an emoji. The CLI proof-mode result printer now
  replaces unencodable characters instead of crashing. No provider/runtime
  behavior, retry/fallback, routing, preflight, session/history, service/API, or
  default CLI behavior was added.

Continuity smoke:

```powershell
python scripts/smoke_providers.py --provider lmstudio_responses_continuity --model <local-model>
```

The continuity target sends two fixed prompts. It requires a non-empty first
response, a first provider response id, a non-empty second response, and a second
provider response id. It does not validate the numeric answer.

## LiteLLM

The LiteLLM target is opt-in only and relies on external LiteLLM/provider
environment configuration. Configure any required credentials outside the smoke
script. The script does not print secrets or environment values.

```powershell
python scripts/smoke_providers.py --provider litellm --model <configured-model>
```

## Local Health/Version API

Task 118 adds a manual developer-only runner for the local health/version API
app object. It is not a service daemon, subprocess supervisor, product runtime,
or CI requirement. It is documented for `GET /health` and `GET /version` smoke
only and defaults to `127.0.0.1:8765`. These health/version endpoints are public
loopback readiness endpoints and do not require the local auth token.

Task 121 adds a protected `/v1/turns` adapter to the app object, but the manual
runner does not provide a fake development token or stub turn handler. Manual
`/v1/turns` smoke remains deferred so this runner stays health/version-only and
does not grow execution composition.

Task 122 adds a RuntimeComposition-owned fake handler factory for `/v1/turns`,
but the manual runner still does not inject it or publish a development bearer
token. Manual fake `/v1/turns` smoke remains deferred to a separate task that
can explicitly document the token, request shape, and expected output.

Task 123 adds a developer-only RuntimeComposition smoke runner for fake
`/v1/turns` execution. It composes the local API runner with the
RuntimeComposition fake handler outside `packages.local_api`. It still defaults
to `127.0.0.1:8765`, uses only a caller-provided fake/dev bearer token, and is
not part of CI or `run_all_checks.py`.

Start the runner from the repository root:

```powershell
python -m packages.local_api.runner
```

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

Check version:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/version
```

Stop the runner from its terminal with `Ctrl+C`.

### Local Fake `/v1/turns` API Smoke

Start the fake-turns smoke runner from the repository root. The token below is
an example fake/dev-only value; do not reuse it as a production secret.

```powershell
python -m packages.runtime_composition.local_api_fake_turns_runner --dev-token local-dev-token
```

Send a valid fake turn request:

```powershell
$body = @'
{
  "schema_version": "0.1.1-draft",
  "execution_mode": "assistant_runtime_fake_provider",
  "assistant_turn_input": {
    "schema_version": "0.1.1-draft",
    "trace_id": "trace-local-api-smoke",
    "turn_id": "turn-local-api-smoke",
    "input_event_id": "event-local-api-smoke",
    "session_ref": null,
    "identity_ref": null,
    "user_visible_input": "Hello through local API fake turns",
    "assistant_mode": "default",
    "policy_context": {
      "requested_capabilities": [],
      "sensitivity": "normal"
    },
    "metadata": {}
  },
  "model": "fake-model",
  "instructions": null,
  "previous_response_id": null,
  "provider_options": {}
}
'@

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/v1/turns `
  -Headers @{ Authorization = "Bearer local-dev-token" } `
  -ContentType "application/json" `
  -Body $body
```

Expected success signs:

- response validates as `AssistantTurnResult`
- `trace_id` and `turn_id` match the request
- `assistant_final_response.text` is the deterministic fake provider response
- `provider_turn_refs[0].provider_name` is `fake`

Missing or wrong auth returns a safe `AUTH_REQUIRED` `ErrorEnvelope` and does
not parse the body:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/v1/turns `
  -ContentType "application/json" `
  -Body $body

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/v1/turns `
  -Headers @{ Authorization = "Bearer wrong-dev-token" } `
  -ContentType "application/json" `
  -Body $body
```

Invalid JSON with valid auth returns a safe validation `ErrorEnvelope`:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/v1/turns `
  -Headers @{ Authorization = "Bearer local-dev-token" } `
  -ContentType "application/json" `
  -Body '{not-json'
```

Expected success signs:

- `/health` returns a `HealthCheck` JSON object with service
  `marvex-local-api`, status `ok`, schema version `0.1.1-draft`, and
  non-negative uptime.
- `/version` returns a `VersionInfo` JSON object with service
  `marvex-local-api`, service version `0.1.0`, and the active health/version
  contract versions.

Expected failure signs:

- Unknown routes return a safe `ErrorEnvelope` with `NOT_FOUND`.
- If the port is already in use, stop the other local process or choose a later
  approved runner enhancement; do not add automatic daemon management here.

Latest manual local fake `/v1/turns` plus trace-read smoke:

- Date: 2026-05-15.
- Command shape:
  `python -m packages.runtime_composition.local_api_fake_turns_runner --dev-token <fake-dev-token>`.
- Fake/dev token behavior: used the documented fake label `local-dev-token`;
  auth error responses did not echo token material.
- Observed `/health`: HTTP 200, service `marvex-local-api`, status `ok`,
  schema version `0.1.1-draft`, non-negative uptime.
- Observed `/version`: HTTP 200, service `marvex-local-api`, service version
  `0.1.0`, schema version `0.1.1-draft`, health/version contract versions
  `0.1.1-draft`.
- Observed `/v1/turns`: HTTP 200 `AssistantTurnResult`, trace id
  `trace-local-api-fake-turns-plus-trace-smoke`, turn id
  `turn-local-api-fake-turns-plus-trace-smoke`, final text `fake provider response`,
  one provider ref with provider `fake` and ref id `fake-response-001`.
- Observed `/v1/traces/{trace_id}` with auth: HTTP 200; same trace id, scope
  `current_process`, source `in_memory`, `event_count` 5, `truncated` false.
- Trace stages/levels summary: `provider_request_created:info`,
  `provider_request_sent:info`, `provider_response_received:info`,
  `final_response_created:info`, `turn_completed:info`.
- Trace envelope fields observed: `schema_version`, `trace_id`, `scope`,
  `source`, `events`, `event_count`, `truncated`.
- Trace projection did not expose raw `TraceEvent.data`, prompt text,
  `provider_response_id`, provider response ref id, bearer token, or provider
  payloads.
- Top-level `provider_response_id` was not present; provider identity surfaced
  through `provider_turn_refs`.
- Missing trace auth returned HTTP 401 `AUTH_REQUIRED` from `local_api` with
  reason `missing`.
- Wrong trace auth returned HTTP 401 `AUTH_REQUIRED` from `local_api` with
  reason `invalid`.
- Safe bounded excerpt:
  `AssistantTurnResult trace-local-api-fake-turns-plus-trace-smoke / turn-local-api-fake-turns-plus-trace-smoke -> fake provider response; trace_events=5`.
- The smoke remains developer-only, fake-provider-only, and outside CI /
  `run_all_checks.py`.

### Local LM Studio `/v1/turns` API Smoke

Task 131 adds the first real-provider local API mode as a separate
developer-only LM Studio Responses runner, not a generic provider router and
not service daemon behavior. The command shape is:

```powershell
python -m packages.runtime_composition.local_api_lmstudio_responses_runner --dev-token <fake-dev-token>
```

Smoke prerequisites and expectations:

- LM Studio is already running at the configured local OpenAI-compatible API.
- A model is loaded and passed explicitly in the request body.
- The protected request uses `execution_mode:
  "assistant_runtime_lmstudio_responses"`.
- `provider_options` remains `{}` unless a later task approves keys.
- `/health` and `/version` remain public.
- `POST /v1/turns` and `GET /v1/traces/{trace_id}` require bearer auth.
- The response validates as `AssistantTurnResult`; any provider reference stays
  in assistant-envelope reference fields, not as a top-level
  `provider_response_id`.
- The trace read returns only safe current-process in-memory projections.
- Missing/wrong auth returns safe `AUTH_REQUIRED` without token echo.

This smoke must remain manual-only and outside `run_all_checks.py`. It
must not record full prompts, raw provider payloads, full provider outputs,
secrets, bearer tokens, environment values, stack traces, or persistent traces.

Latest manual local LM Studio `/v1/turns` plus trace-read smoke:

- Date: 2026-05-16.
- Command shape:
  `python -m packages.runtime_composition.local_api_lmstudio_responses_runner --dev-token <fake-dev-token>`.
- Model used: `qwen3.5-0.8b`.
- LM Studio setup: local server started on `127.0.0.1:1234`; model loaded with
  identifier `qwen3.5-0.8b`; server was stopped after the smoke.
- Fake/dev token behavior: used the documented fake label `local-dev-token`;
  auth error responses did not echo token material.
- Observed `/health`: HTTP 200, service `marvex-local-api`, status `ok`,
  schema version `0.1.1-draft`.
- Observed `/version`: HTTP 200, service `marvex-local-api`, service version
  `0.1.0`, schema version `0.1.1-draft`.
- Observed `/v1/turns`: HTTP 200 `AssistantTurnResult` with nested provider
  error, trace id `trace-local-api-lmstudio-smoke-132`, turn id
  `turn-local-api-lmstudio-smoke-132`, no final assistant response, one provider
  ref for `lmstudio_responses`, and no top-level `provider_response_id`.
- Underlying provider smoke result: `lmstudio_responses` failed with
  `PROVIDER_ERROR (AuthenticationError)` because the current LM Studio server
  requires a valid local API token and rejected the placeholder SDK key.
- Observed `/v1/traces/{trace_id}` with auth: HTTP 200; same trace id, scope
  `current_process`, source `in_memory`, `event_count` 4, `truncated` false.
- Trace stages/levels summary: `provider_request_created:info`,
  `provider_request_sent:info`, `provider_response_received:error`,
  `turn_failed:error`.
- Trace envelope fields observed: `schema_version`, `trace_id`, `scope`,
  `source`, `events`, `event_count`, `truncated`.
- Trace projection did not expose raw `TraceEvent.data`, prompt text,
  `provider_response_id`, bearer token, secrets, provider payloads, or provider
  raw previews.
- Missing/wrong `/v1/turns` auth returned HTTP 401 `AUTH_REQUIRED` with reasons
  `missing` and `invalid`.
- Missing/wrong `/v1/traces/{trace_id}` auth returned HTTP 401 `AUTH_REQUIRED`
  with reasons `missing` and `invalid`.
- Safe bounded excerpt:
  `AssistantTurnResult trace-local-api-lmstudio-smoke-132 / turn-local-api-lmstudio-smoke-132 -> nested PROVIDER_ERROR; trace_events=4`.
- No runtime code changed. A later provider configuration task should decide how
  to supply LM Studio local API tokens without adding generic API-key policy to
  Local API or RuntimeComposition.

Task 133 LM Studio token configuration decision:

- Task 132 proved local API auth, `/v1/turns`, mapped provider-error response,
  and same-process trace read; live success was blocked by LM Studio requiring a
  valid provider token.
- Provider tokens belong only to the LM Studio adapter config, ProviderRuntime
  construction, and explicit developer-only RuntimeComposition pass-through.
- Local API, Core, AssistantRuntime, ports, contracts, telemetry projection, CLI
  default paths, services, request bodies, metadata, and `provider_options`
  remain provider-token blind.
- Provider tokens must never be logged, persisted, echoed in errors, included in
  traces/provider refs, copied into metadata, or recorded in smoke output.
- Rollback path: remove the ProviderRuntime credential field and runner
  environment read, returning to placeholder-key safe provider-error behavior.

Task 134 LM Studio token configuration implementation:

- ProviderRuntimeConfig now has the LM Studio-only field
  `lmstudio_responses_api_key`.
- For `provider_name="lmstudio_responses"`, ProviderRuntime maps a configured
  value to `LMStudioResponsesProviderConfig(api_key=...)`.
- Non-LM-Studio providers reject `lmstudio_responses_api_key`.
- The developer-only LM Studio local API runner reads
  `MARVEX_LMSTUDIO_API_KEY` without printing or recording its value and passes
  it through RuntimeComposition to ProviderRuntime.
- If `MARVEX_LMSTUDIO_API_KEY` is missing or blank, behavior remains
  deterministic: the runner passes no provider token override and the adapter
  keeps its existing placeholder SDK key behavior.
- The `/v1/turns` request body remains unchanged; provider credentials remain
  forbidden in request bodies and `provider_options`.
- Provider exception messages redact the configured adapter API key if provider
  exception text includes it.

Recommended manual smoke setup after Task 134:

```powershell
$env:MARVEX_LMSTUDIO_API_KEY="<real-local-lmstudio-token>"
python -m packages.runtime_composition.local_api_lmstudio_responses_runner --dev-token local-dev-token
```

Do not record the token value or environment dump in smoke notes. Record only
whether the provider token environment variable was present.

Latest token-backed manual local LM Studio `/v1/turns` plus trace-read smoke:

- Date: 2026-05-16.
- Command shape:
  `python -m packages.runtime_composition.local_api_lmstudio_responses_runner --dev-token <fake-dev-token>`.
- Provider token source: `MARVEX_LMSTUDIO_API_KEY` present in local environment;
  token value not printed, recorded, or copied into docs.
- Model used: `qwen3.5-0.8b`.
- Observed `/health`: HTTP 200, `marvex-local-api:ok`.
- Observed `/version`: HTTP 200, `marvex-local-api:0.1.0`.
- Observed `/v1/turns`: HTTP 200 `AssistantTurnResult` success with trace id.
- Observed trace read: HTTP 200, `current_process`, `in_memory`,
  `event_count` 5, `truncated` false.
- Trace stages/levels summary: `provider_request_created:info`,
  `provider_request_sent:info`, `provider_response_received:info`,
  `final_response_created:info`, `turn_completed:info`.
- Missing/wrong auth returned HTTP 401 for both protected routes.
- Trace safety check: no provider token value, raw provider payload, raw
  environment value, full prompt/transcript, stack trace, or auth material.
- No runtime behavior changed.

Latest manual local health/version runner smoke:

- Date: 2026-05-13.
- Command shape: `python -m packages.local_api.runner`.
- Result: success; `/health` and `/version` both responded on
  `http://127.0.0.1:8765`.
- Observed `/health`: service `marvex-local-api`, status `ok`, schema version
  `0.1.1-draft`.
- Observed `/version`: service `marvex-local-api`, service version `0.1.0`,
  schema version `0.1.1-draft`.
- This remains manual smoke only and is not part of CI or `run_all_checks.py`.
