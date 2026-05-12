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
- The mode builds an assistant-turn input, injects a local deterministic
  send-capable provider double, and calls the Core assistant-runtime
  provider-stage skeleton.
- It is not the default CLI path, does not use ProviderRuntime as a production
  bridge, and does not introduce provider routing, sessions, history, services,
  APIs, or product behavior.
- `--assistant-runtime-provider-stage-trace` enables in-memory test/dev trace
  emission only; no telemetry storage or logging sink is added.

Decision diagnostics are not a CLI surface. The CLI must not import decision
runtime or decision adapter modules.

Forbidden responsibilities:

- Core orchestration.
- Provider logic.
- Provider SDK calls.
- Provider behavior, routing policy, fallback policy, retries, or provider runtime logic.
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
- May depend on ProviderRuntime for approved provider creation.
- May depend on ProcessRuntime only for approved local health/version commands.
- May use approved assistant-turn contracts for explicit dev-only
  assistant-runtime provider-stage input construction.
- Must not depend on provider SDKs, telemetry implementation, or services.
- Any future provider selection expansion must stay inside the dedicated ProviderRuntime boundary.
- Task 110 decides that future real ProviderRuntime-backed assistant-runtime
  composition should be delegated to a separate runtime composition/factory
  layer, not owned directly by CLI.
