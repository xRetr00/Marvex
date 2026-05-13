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
or CI requirement. It exposes only `GET /health` and `GET /version` and defaults
to `127.0.0.1:8765`.

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
