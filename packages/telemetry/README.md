# Telemetry Package

Status: minimal Provider Foundation lifecycle implementation plus local-only
in-memory trace reader and telemetry-owned local persistence foundation.

Ownership: Trace and diagnostics boundary.

Responsibility: Provide `TelemetrySink`, `NoopTelemetrySink`, trace event
construction for the v1 turn lifecycle, sanitizer primitives, and
structured-output-shaped trace data safety inside telemetry event construction.
Task 127 also adds `InMemoryTraceReader` for injected current-process trace
reads. Task 146 adds `PersistentTraceStore` for local NDJSON persistence with
redaction before write and bounded file rotation.

Forbidden responsibilities:

- Persistence outside telemetry ownership.
- Logging sinks outside the approved local trace persistence store.
- Core orchestration.
- Provider behavior.
- CLI interaction.
- Tool execution.
- Future module domains outside trace diagnostics.
- Logging secrets or raw sensitive transcripts by default.
- Sessions/history, memory, tools, UI, voice, desktop, vision, proactive
  behavior, generic provider routing, retry/fallback, model selection, daemon
  supervision, WebSocket/events, or remote trace access.

Dependency direction:

- May depend on approved contracts.
- Must remain isolated from adapters, CLI, and services.
- Local API receives telemetry readers only by injection and must not import or
  own persistence internals.

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

Task 127 implementation:

- `InMemoryTraceReader` is an instance-owned current-process `TelemetrySink`
  and reader.
- `emit(...)` records events by trace id inside that instance only.
- `read_trace(...)` returns a safe local API envelope with `schema_version`,
  `trace_id`, `scope`, `source`, `events`, `event_count`, and `truncated`.
- Event projections exclude raw `TraceEvent.data`, provider payloads, provider
  response ids, prompts/messages, auth material, stack traces, secrets, file
  contents, and environment data.
- Event projections may include safe `session_ref` and `conversation_ref`
  objects when they use only `ref_type` plus safe `ref_id`; telemetry still does
  not own session lifecycle, transcripts, or history.
- Task 128 uses the same instance as both the fake-turn telemetry sink and trace
  reader in the developer-only local API fake runner. That remains
  current-process-only and disappears when the process exits.
- Task 130 decides that a future LM Studio Responses local API manual runner
  should use the same explicit current-process `InMemoryTraceReader` pattern.
  It must not add persistence, a global trace store, cross-process lookup,
  search, streaming, or raw provider/secret exposure.
- Task 131 implements that manual runner injection pattern.

Telemetry persistence foundation:

- `PersistentTraceStore` is a telemetry-owned `TelemetrySink` plus trace reader.
- It writes newline-delimited JSON records to an explicit local-user-scoped file
  path.
- It sanitizes event messages and `TraceEvent.data` before writing.
- It rejects non-JSON-compatible event data before creating a file.
- It rotates local files by size with a bounded rotated-file count.
- Read envelopes use `scope: "local_persistence"` and `source: "local_file"`.
- Read envelopes may project safe `session_ref` and `conversation_ref` linkage
  from sanitized event data without returning raw session bodies or transcripts.
- Malformed stored records are counted and skipped; raw malformed text is not
  returned.
- Write failures raise `TelemetryPersistenceError` with
  `TELEMETRY_WRITE_FAILED` and no raw event or secret details.
- The store is not wired into default runtime, Local API, RuntimeComposition,
  Core, ProviderRuntime, CLI, or services.
