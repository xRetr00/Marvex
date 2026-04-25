# CLI App

Status: v1 one-shot CLI.

Ownership: Command-line client boundary.

Responsibility: Terminal request submission to Core for a single text turn.

Forbidden responsibilities:

- Core orchestration.
- Provider logic.
- Provider SDK calls.
- Provider behavior, routing policy, fallback policy, retries, or provider runtime logic.
- Concrete provider adapter imports.
- HTTP server behavior.
- Tool execution.
- Memory, intent, voice, UI shell, desktop context, or proactive behavior.
- Session storage or history management.

Dependency direction:

- May depend on public Core orchestration.
- May depend on ProviderRuntime for approved provider creation.
- Must not depend on provider SDKs, telemetry implementation, or services.
- Any future provider selection expansion must stay inside the dedicated ProviderRuntime boundary.
