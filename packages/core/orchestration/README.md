# Core Orchestration Package

Status: skeleton only.

Ownership: Core turn orchestration boundary.

Responsibility: Future coordination of approved turn lifecycle steps through contracts and ports.

Forbidden responsibilities:

- Provider-specific logic.
- Provider payload construction.
- HTTP calls.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Hidden global state.

Dependency direction:

- May depend on approved contracts and ports only.
- Must not depend on adapters, CLI, telemetry implementation, services, or future workers.

