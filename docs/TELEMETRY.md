# Telemetry

Telemetry is a v1 foundation feature, not an afterthought.

## Required Fields

Every trace event must include:

- `schema_version`
- `trace_id`
- `event_id`
- `timestamp`
- `stage`
- `level`
- `message`
- `data`

## Required Lifecycle Events

V1 turn lifecycle:

- `turn_received`
- `provider_request_created`
- `provider_request_sent`
- `provider_response_received`
- `final_response_created`
- `turn_completed`
- `turn_failed`

## Trace Rules

- One turn has one `trace_id`.
- The CLI must display the `trace_id`.
- Provider adapters must receive and return the same `trace_id`.
- Errors must include `trace_id`.
- Future subprocesses must propagate `trace_id` across IPC.

## Storage

V1 may start with local structured log files. The storage choice must be documented before implementation.

Default V1 storage:

- Location: `.marvex/logs/` under the workspace or configured user data directory.
- Format: newline-delimited JSON trace events.
- Retention: keep at most 7 days or 50 MB by default, whichever is reached first.
- Rotation: rotate when a log file reaches 5 MB or at process start after a date change.
- Access: local process only; trace APIs require local auth.

## Privacy And Redaction

Telemetry must be useful for debugging without becoming a transcript or secrets store.

Redact by default:

- auth tokens and API keys
- environment variables
- file contents
- full prompts or provider outputs unless a task explicitly enables diagnostic capture
- personal data detected in metadata
- stack traces containing local secrets or absolute private paths
- provider raw payload fields not required for debugging

Allowed by default:

- ids
- lifecycle stages
- enum values
- timings
- service names
- error codes
- redacted error messages
- aggregate token or usage counts when provided by a provider

Secrets and PII must never be logged by default. Diagnostic modes that capture sensitive text require an explicit task spec, visible warning, retention limit, and redaction review.

## Failure Behavior

- Telemetry write failure must emit or return `TELEMETRY_WRITE_FAILED` if the turn can continue safely.
- Telemetry failure must not silently swallow errors.
- If telemetry is required for an acceptance test, failure must fail that test.
- The Core must not retry telemetry writes forever.
- Telemetry failure must not corrupt turn state.

## Forbidden

- Free-form print debugging as the only diagnostic trail.
- Silent retries.
- Swallowed exceptions.
- Logs without trace IDs.
- Logging auth tokens, secrets, raw environment variables, or full sensitive transcripts by default.
