# CLI App

Status: skeleton only.

Ownership: Command-line client boundary.

Responsibility: Future terminal interaction and request submission to Core.

Forbidden responsibilities:

- Core orchestration.
- Provider logic.
- HTTP server behavior.
- Tool execution.
- Memory, intent, voice, UI shell, desktop context, or proactive behavior.

Dependency direction:

- May depend on Core when implementation is approved.
- Must not depend on adapters, provider SDKs, telemetry implementation, or services.
