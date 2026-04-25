# Telemetry Package

Status: skeleton only.

Ownership: Trace and diagnostics boundary.

Responsibility: Future trace lifecycle and structured diagnostics after contract approval.

Forbidden responsibilities:

- Core orchestration.
- Provider behavior.
- CLI interaction.
- Tool execution.
- Future module domains outside trace diagnostics.
- Logging secrets or raw sensitive transcripts by default.

Dependency direction:

- Must remain isolated from Core, adapters, CLI, and services.
- May depend on approved contracts after telemetry contract approval.
