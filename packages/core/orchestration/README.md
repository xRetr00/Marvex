# Core Orchestration Package

Status: minimal Provider Foundation implementation.

Ownership: Core turn orchestration boundary.

Responsibility: Coordinate the approved v1 turn lifecycle through contracts,
an injected provider port, and injected/noop telemetry sinks.

Forbidden responsibilities:

- Provider-specific logic.
- Provider runtime selection.
- HTTP calls.
- Tool execution.
- Future module domains outside turn coordination.
- Hidden global state.

Dependency direction:

- May depend on approved contracts, provider ports, and telemetry sink contracts.
- Must not depend on concrete integrations, user-facing callers, process
  boundaries, or future workers.
