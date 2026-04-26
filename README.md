# Marvex

<p align="center">
  <img src="assets/logo.png" alt="Marvex logo" width="300" />
</p>

Marvex is a service-ready modular desktop system. It starts as a Python Core
Service with a CLI client, provider adapters, and telemetry, then grows into a
process-ready desktop application where major modules can be replaced, disabled,
or moved into subprocesses.

`PROJECT_STATUS.md` is authoritative for the current phase and allowed work.
Implementation is allowed only through approved task slices with contracts,
tests, validation scripts, and final reports.

AI agents must run the validation scripts before finishing any task, including a
one-line hotfix. The required command is:

```powershell
python scripts/run_all_checks.py
```

The user is not expected to review code correctness. Agents must not rely on
user code review as a safety mechanism. Every implementation step must be
controlled by contracts, task specs, tests, validation scripts, and a final
report.

## Current Implementation

Provider Foundation is implemented:

- Pydantic contract models and JSON schema generation.
- `ProviderPort` as a tiny contract-only provider boundary.
- Deterministic `FakeProvider`.
- `LiteLLMProvider` isolated behind the provider adapter boundary.
- `LMStudioResponsesProvider` isolated behind the provider adapter boundary and
  using the OpenAI Python SDK against LM Studio's OpenAI-compatible Responses API.
- `ProviderRuntime` as the only approved provider creation boundary.
- `TurnOrchestrator` for minimal Core turn orchestration through `ProviderPort`.
- Minimal telemetry lifecycle events through `TelemetrySink` and
  `NoopTelemetrySink`.
- One-shot CLI vertical slice.
- Manual provider smoke harness with fake, LiteLLM, and LM Studio targets.

## Current Boundary

Allowed now:

- Documentation, templates, and validation scripts.
- README/status/library/schema governance cleanup.
- Approved task slices only.
- Service placeholder READMEs.

Forbidden now:

- Unapproved product behavior changes.
- Provider behavior changes outside approved adapter tasks.
- CLI behavior changes outside approved API tasks.
- Telemetry runtime behavior changes outside approved telemetry tasks.
- UI code.
- Tool execution.
- Memory systems.
- Voice, vision, desktop context, proactive behavior.

A roadmap entry, task id, or placeholder README is not permission to implement.
The next subsystem after Task 018 cleanup is Process Readiness.
