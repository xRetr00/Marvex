# CLI App

Status: v1 one-shot CLI with local health/version commands.

Ownership: Command-line client boundary.

Responsibility: Terminal request submission to Core for a single text turn, plus
local process readiness health/version reporting from explicit in-memory
runtime config.

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
- Must not depend on provider SDKs, telemetry implementation, or services.
- Any future provider selection expansion must stay inside the dedicated ProviderRuntime boundary.
