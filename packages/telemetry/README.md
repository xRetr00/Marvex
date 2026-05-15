# Telemetry Package

Status: minimal Provider Foundation lifecycle implementation.

Ownership: Trace and diagnostics boundary.

Responsibility: Provide `TelemetrySink`, `NoopTelemetrySink`, trace event
construction for the v1 turn lifecycle, sanitizer primitives, and
structured-output-shaped trace data safety inside telemetry event construction.

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
- `sinks.py` applies sanitizer safety inside `make_trace_event(...)` when trace
  data is shaped like structured-output diagnostics.
- unsafe trace fields are redacted to `"[REDACTED]"`.
- raw provider output, raw previews, parsed payloads, prompts, transcripts,
  provider/session/thread identifiers, auth tokens, and secrets are not safe for
  default telemetry.
- this wiring does not add runtime product behavior, logging sinks, or
  persistent storage.

Trace exposure decision:

- Task 126 decides that the first future trace API should read only from an
  explicitly injected current-process in-memory telemetry recording sink/store.
- Telemetry owns trace recording, lookup, and read-time sanitization.
- Local API may serialize only a safe envelope/projection provided through an
  injected reader; it must not own trace storage.
- Persistent storage, trace streaming, cross-process/session lookup, and raw
  trace-object exposure remain blocked.
