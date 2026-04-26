# Telemetry Package

Status: minimal Provider Foundation lifecycle implementation.

Ownership: Trace and diagnostics boundary.

Responsibility: Provide `TelemetrySink`, `NoopTelemetrySink`, and trace event
construction for the v1 turn lifecycle.

Forbidden responsibilities:

- Persistent trace storage until an approved storage task exists.
- Core orchestration.
- Provider behavior.
- CLI interaction.
- Tool execution.
- Future module domains outside trace diagnostics.
- Logging secrets or raw sensitive transcripts by default.

Dependency direction:

- May depend on approved contracts.
- Must remain isolated from adapters, CLI, and services.
