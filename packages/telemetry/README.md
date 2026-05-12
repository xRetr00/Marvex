# Telemetry Package

Status: minimal Provider Foundation lifecycle implementation.

Ownership: Trace and diagnostics boundary.

Responsibility: Provide `TelemetrySink`, `NoopTelemetrySink`, trace event
construction for the v1 turn lifecycle, and sanitizer primitives for future
safe trace data handling.

Forbidden responsibilities:

- Persistent trace storage until an approved storage task exists.
- Logging sinks until an approved logging/storage task exists.
- Core orchestration.
- Provider behavior.
- CLI interaction.
- Tool execution.
- Future module domains outside trace diagnostics.
- Logging secrets or raw sensitive transcripts by default.

Dependency direction:

- May depend on approved contracts.
- Must remain isolated from adapters, CLI, and services.

Sanitization:

- `sanitization.py` owns `sanitize_trace_data(...)` and
  `assert_trace_data_safe(...)`.
- unsafe trace fields are redacted to `"[REDACTED]"`.
- raw provider output, raw previews, parsed payloads, prompts, transcripts,
  provider/session/thread identifiers, auth tokens, and secrets are not safe for
  default telemetry.
- the sanitizer is not wired into runtime behavior or persistent storage.
