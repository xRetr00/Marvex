# Core Orchestration Package

Status: skeleton only.

Ownership: Core turn orchestration boundary.

Responsibility: Future coordination of approved turn lifecycle steps through contracts and ports.

Forbidden responsibilities:

- Provider-specific logic.
- Provider payload construction.
- HTTP calls.
- Tool execution.
- Future module domains outside turn coordination.
- Hidden global state.

Dependency direction:

- May depend on approved contracts and ports only.
- Must not depend on concrete integrations, clients, diagnostics runtime, services, or future workers.
