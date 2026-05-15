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

Current Provider Foundation implementation emits lifecycle events through the
`TelemetrySink` protocol. The default runtime sink is `NoopTelemetrySink`, and
tests may inject recording sinks.

No default persistent telemetry storage is implemented yet. Persistent trace
storage is future explicit work and requires its own approved task spec before
implementation.

Future storage guidance:

- Location: `.marvex/logs/` under the workspace or configured user data directory.
- Format: newline-delimited JSON trace events.
- Retention: keep at most 7 days or 50 MB by default, whichever is reached first.
- Rotation: rotate when a log file reaches 5 MB or at process start after a date change.
- Access: local process only; trace APIs require local auth.

Task 126 decides the first future trace exposure path. Before any real-provider
local API turn mode, Marvex should add a protected current-process trace read
path backed by an explicitly injected in-memory telemetry recording sink/store.
That store and read-time safety belong to `packages.telemetry`, not Local API
or RuntimeComposition. The first read path must not implement persistence,
cross-process lookup, session history, global state, or trace streaming.

## Privacy And Redaction

Telemetry must be useful for debugging without becoming a transcript or secrets store.

Task 101 adds a telemetry-owned sanitizer primitive:

- `packages.telemetry.sanitization.sanitize_trace_data(...)`
- `packages.telemetry.sanitization.assert_trace_data_safe(...)`

Task 102 wires the sanitizer into `packages.telemetry.sinks.make_trace_event(...)`
for structured-output-shaped trace data. The path is telemetry-owned: callers
do not own redaction policy, ProviderRuntime and provider adapters do not import
telemetry sanitization, and normal provider-turn trace data keeps its existing
shape unless it is structured-output trace data.

Task 103 adds an explicit AssistantRuntime structured-output result helper that
may emit structured-output consumption diagnostics through `make_trace_event(...)`.
The helper does not own redaction policy; unsafe trace data is still handled by
the telemetry event construction path.

Task 104 proves the ProviderRuntime/provider_structured_output-to-AssistantRuntime
bridge only through integration tests. The proof reuses the existing
AssistantRuntime helper and telemetry event construction path; it does not add
a telemetry sink, storage behavior, or caller-owned redaction policy.

Task 105 adds an explicit AssistantRuntime provider-stage skeleton that may emit
provider-stage lifecycle diagnostics through `make_trace_event(...)`. The path
does not add telemetry storage or caller-owned redaction policy.

Task 106 adds a Core-owned internal wiring skeleton that delegates to the
AssistantRuntime provider-stage helper. Trace lifecycle diagnostics still flow
through the AssistantRuntime helper and `make_trace_event(...)`; Core does not
own telemetry redaction policy, storage, or a new product sink.

Tasks 107 and 109 add and stabilize an explicit CLI fake-provider
AssistantRuntime foundation mode. The mode may pass an in-memory test/dev sink
into the Core-to-AssistantRuntime provider-stage path. Trace events still go
through `make_trace_event(...)`; no telemetry storage or caller-owned redaction
policy is added.

This is trace event construction safety only. It does not implement telemetry
storage, logging sinks, ProviderRuntime behavior, AssistantRuntime normal-turn
behavior, default CLI behavior, services, API/WebSocket, UI, or product runtime
behavior.

Redaction convention:

- unsafe fields are replaced with the stable marker `"[REDACTED]"`.
- non-JSON-compatible trace data is rejected.
- inputs are not mutated in place.

Redact by default:

- auth tokens and API keys
- environment variables
- file contents
- full prompts or provider outputs unless a task explicitly enables diagnostic capture
- personal data detected in metadata
- stack traces containing local secrets or absolute private paths
- provider raw payload fields not required for debugging
- raw provider output
- raw previews
- parsed structured-output payloads
- prompt, message-list, conversation, and transcript payloads
- provider response ids, previous response ids, session ids, conversation ids,
  and thread ids
- bearer/auth/token/secret/password-bearing fields

Allowed by default:

- trace, turn, and event ids
- lifecycle stages
- enum values
- timings
- service names
- error codes
- redacted error messages
- aggregate token or usage counts when provided by a provider
- structured-output summaries such as state, handoff status, consumption
  status, target contract, sanitized message, sanitized error code, and
  diagnostic-only flags when they pass sanitizer checks

Structured-output trace data must use sanitized summaries only. When
structured-output-shaped data is passed to `make_trace_event(...)`, raw provider
output, raw previews, parsed payloads, prompts, transcripts, provider/session
identifiers, auth tokens, and secrets are redacted before the `TraceEvent` is
created. Non-JSON-compatible structured-output trace data is rejected.

Future trace API reads must apply the same safety posture at read time. The API
must return a local envelope with sanitized trace-event projections, not raw
internal trace objects. Raw prompts, provider payloads, provider response ids,
session/history bodies, auth material, secrets, stack traces, and unsanitized
`TraceEvent.data` must not be exposed over HTTP.

Future structured-output runtime integration must still name the exact caller,
data shape, sink behavior, failure behavior, and boundary tests before emitting
new trace events.

Secrets and PII must never be logged by default. Diagnostic modes that capture
sensitive text require an explicit task spec, visible warning, retention limit,
and redaction review.

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
