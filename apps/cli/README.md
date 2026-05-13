# CLI App

Status: v1 one-shot CLI with local health/version commands.

Ownership: Command-line client boundary.

Responsibility: Terminal request submission to Core for a single text turn, plus
local process readiness health/version reporting from explicit in-memory
runtime config.

AssistantRuntime fake-provider foundation mode:

- `--assistant-runtime-fake-provider` is the official explicit foundation mode
  for exercising the AssistantRuntime provider-stage path from CLI.
- The Task 107 flag `--assistant-runtime-provider-stage-fake` remains supported
  as a compatibility alias.
- The mode builds an assistant-turn input and calls
  `packages.runtime_composition.run_fake_provider_assistant_bridge(...)`.
- RuntimeComposition owns fake-provider composition for this mode; CLI does not
  create the fake provider or call ProviderRuntime directly.
- It is not the default CLI path and does not introduce real provider-backed
  AssistantRuntime behavior, provider routing, sessions, history, services,
  APIs, or product behavior.
- `--assistant-runtime-provider-stage-trace` enables in-memory test/dev trace
  emission only; no telemetry storage or logging sink is added.

AssistantRuntime LM Studio Responses proof mode:

- `--assistant-runtime-lmstudio-responses` is an explicit non-default proof mode
  for exercising the RuntimeComposition LM Studio Responses AssistantRuntime
  bridge from CLI.
- The mode builds an assistant-turn input and calls
  `packages.runtime_composition.run_lmstudio_responses_assistant_bridge(...)`.
- RuntimeComposition owns ProviderRuntime composition for this mode; CLI does
  not create providers, import ProviderRuntime, import provider adapters, route
  providers, retry/fallback, manage sessions/history, read API keys, or select
  models beyond passing the explicit `--model` value.
- Automated tests mock the bridge; live LM Studio execution is manual smoke only
  and is not part of `run_all_checks.py`.
- It is not default CLI behavior, service/API behavior, or product behavior.
- Failure output is bounded to safe message, error code, provider response ref
  when present, trace id, and turn id. LM Studio unavailable/model rejected,
  timeout-like, provider error, empty output, and malformed response cases use
  existing Core/AssistantRuntime error mapping; CLI does not add preflight,
  retry, fallback, routing, session/history, model-selection, or API-key policy.

Decision diagnostics are not a CLI surface. The CLI must not import decision
runtime or decision adapter modules.

Forbidden responsibilities:

- Core orchestration.
- Provider logic.
- Provider SDK calls.
- Provider behavior, routing policy, fallback policy, retries, or provider runtime logic.
- Provider factory/composition ownership.
- Concrete provider adapter imports.
- HTTP server behavior.
- Service mode behavior.
- Provider health checks or dependency probing.
- Config file or environment loading.
- Tool execution.
- Memory, intent, voice, UI shell, desktop context, or proactive behavior.
- Session storage or history management.

Dependency direction:

- May depend on public Core orchestration.
- May depend on RuntimeComposition for approved CLI bridge calls.
- May depend on ProcessRuntime only for approved local health/version commands.
- May use approved assistant-turn contracts for explicit dev-only
  assistant-runtime provider-stage input construction.
- Must not depend on ProviderRuntime, concrete provider adapters, provider SDKs,
  telemetry implementation, or services.
- Any future provider selection expansion must stay inside dedicated runtime
  composition and ProviderRuntime boundaries.
- Task 110 decides that future real ProviderRuntime-backed assistant-runtime
  composition should be delegated to a separate runtime composition/factory
  layer, not owned directly by CLI.
- Task 112 wires the official fake-provider foundation mode to RuntimeComposition
  while preserving the compatibility alias and default CLI output behavior.
- Task 114 adds the explicit LM Studio Responses AssistantRuntime proof mode
  through RuntimeComposition while keeping default CLI behavior unchanged.
- Task 115 documents the manual live-smoke checklist and failure policy for
  that proof mode without changing default CLI behavior.
