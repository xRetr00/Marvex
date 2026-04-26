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
