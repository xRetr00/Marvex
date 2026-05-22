# Contracts

All contracts are JSON-compatible. Product code must not invent private shapes for the same data.

Contracts are implementation-draft until listed in `docs/CONTRACT_APPROVALS.md`.

Current provider-foundation contracts are listed in `docs/CONTRACT_APPROVALS.md`; they are not full assistant-turn contracts. `TurnInput`, `TurnOutput`, `ProviderRequest`, `ProviderResponse`, and `FinalResponse` must not be silently repurposed as full assistant-turn contracts.
Assistant-level contract planning lives in `docs/ASSISTANT_TURN_CONTRACT_MAP.md`.
The smallest assistant envelope lives in `docs/ASSISTANT_TURN_ENVELOPE.md`.
Assistant envelope schemas live in `docs/ASSISTANT_TURN_CONTRACTS.md`.

## General Validation Rules

- `schema_version`, `trace_id`, and `turn_id` are required wherever listed.
- Required fields must be present even when their value is `null`.
- Optional fields must be explicitly marked optional in this document before implementation.
- Unknown fields are allowed only inside `metadata`, `provider_options`, `raw_metadata`, `details`, or `data`.
- Empty strings are invalid for ids, enum fields, and service names.
- Timestamps must use ISO 8601 UTC.
- Objects must be JSON objects, not encoded JSON strings.

## Compatibility Rules

- Adding an optional field is backward compatible.
- Adding a required field is a breaking change.
- Removing a field is a breaking change.
- Renaming a field is a breaking change.
- Changing nullability is a breaking change unless it only permits `null` for a previously optional field.
- Changing enum meaning is a breaking change.
- Breaking changes require `templates/CONTRACT_CHANGE.md`, migration plan, rollback plan, and replay tests.

## Common Enums

- `source`: `cli`.
- `response_type`: `text`, `error`.
- `finish_reason`: `stop`, `length`, `cancelled`, `error`, `unknown`.
- `stage`: `turn_received`, `provider_request_created`, `provider_request_sent`, `provider_response_received`, `final_response_created`, `turn_completed`, `turn_failed`.
- `level`: `debug`, `info`, `warning`, `error`.
- `status`: `ok`, `degraded`, `starting`, `stopping`, `error`.
- `recoverable`: boolean.

## Error Code Taxonomy

Error codes are stable uppercase strings grouped by source:

- `VALIDATION_ERROR`: input or contract validation failed.
- `AUTH_REQUIRED`: local IPC auth token is missing or invalid.
- `NOT_FOUND`: requested trace, resource, or endpoint target does not exist.
- `PROVIDER_UNAVAILABLE`: provider adapter or provider backend is unavailable.
- `PROVIDER_ERROR`: provider returned an error response.
- `PROVIDER_TIMEOUT`: provider request exceeded timeout.
- `TELEMETRY_WRITE_FAILED`: required telemetry write failed.
- `SERVICE_UNHEALTHY`: health check reports degraded or error.
- `INTERNAL_ERROR`: unexpected implementation error.

New error codes require contract review.

## TurnInput

Purpose: User input entering the Core turn lifecycle.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `turn_id`: string, required, non-empty.
- `input_text`: string, required, may be empty only if a future input mode listed in `docs/CONTRACT_APPROVALS.md` defines that behavior.
- `previous_response_id`: string or null, required, nullable.
- `source`: string enum, required, initially `cli`.
- `metadata`: object, required, may be empty.

Owner: Core contract package.

Can read: CLI, Core, telemetry.

Can write: CLI client.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "turn_id": "turn-001",
  "input_text": "Hello",
  "previous_response_id": null,
  "source": "cli",
  "metadata": {}
}
```

## TurnOutput

Purpose: Complete result of a Core turn.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `turn_id`: string, required, non-empty.
- `final_response`: FinalResponse, required.
- `provider_response_id`: string or null, required, nullable.
- `events`: array of TraceEvent summaries, required, may be empty.
- `error`: ErrorEnvelope or null, required, nullable.

Owner: Core contract package.

Can read: CLI, Shell later, telemetry.

Can write: Core only.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "turn_id": "turn-001",
  "final_response": {
    "text": "Hello.",
    "response_type": "text",
    "finish_reason": "stop",
    "safe_for_tts": true,
    "metadata": {}
  },
  "provider_response_id": "resp-001",
  "events": [],
  "error": null
}
```

## FinalResponse

Purpose: User-facing final assistant response.

Fields:

- `text`: string, required.
- `response_type`: string enum, required.
- `finish_reason`: string enum, required.
- `safe_for_tts`: boolean, required.
- `metadata`: object, required, may be empty.

Owner: Core contract package.

Can read: CLI, Shell later, telemetry.

Can write: Core after provider response normalization.

## ProviderRequest

Purpose: Provider-agnostic request sent from Core to a provider adapter.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `turn_id`: string, required, non-empty.
- `model`: string, required, non-empty.
- `input_text`: string, required.
- `instructions`: string or null, required, nullable.
- `previous_response_id`: string or null, required, nullable.
- `provider_options`: object, required, may be empty.

Owner: Provider port contract.

Can read: provider adapters, telemetry.

Can write: Core only.

Conversation continuity:

- CLI may pass `previous_response_id` for simple sessions through `TurnInput.previous_response_id`.
- Core may copy `TurnInput.previous_response_id` into `ProviderRequest.previous_response_id` after validation.
- Core returns `provider_response_id` in `TurnOutput`.
- Core must not maintain hidden global conversation history in v1.
- A future session store must be explicit, contract-owned, and listed in `docs/CONTRACT_APPROVALS.md` before implementation.

## ProviderResponse

Purpose: Provider-agnostic response returned to Core.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `turn_id`: string, required, non-empty.
- `provider_name`: string, required, non-empty.
- `response_id`: string or null, required, nullable.
- `output_text`: string, required.
- `finish_reason`: string enum, required.
- `usage`: object, required, may be empty.
- `raw_metadata`: object, required, may be empty.
- `error`: ErrorEnvelope or null, required, nullable.

Owner: Provider port contract.

Can read: Core, telemetry.

Can write: provider adapter only.

## TraceEvent

Purpose: Structured lifecycle event for debugging, replay, and audit.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `event_id`: string, required, non-empty.
- `timestamp`: string, required, ISO 8601 UTC.
- `stage`: string enum, required.
- `level`: string enum, required.
- `message`: string, required.
- `data`: object, required, may be empty.

Owner: telemetry package.

Can read: Core, CLI, Shell later, tests.

Can write: telemetry layer and approved emitters.

## ErrorEnvelope

Purpose: Stable error shape across services and adapters.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `error_id`: string, required, non-empty.
- `code`: string enum from the error taxonomy, required.
- `message`: string, required, safe for logs.
- `recoverable`: boolean, required.
- `source`: string, required, non-empty.
- `details`: object, required, may be empty and must be redacted by default.

Owner: contracts package.

Can read: all modules.

Can write: module that detects the error.

## HealthCheck

Purpose: Runtime liveness and readiness status for a service.

This contract exists now for process readiness. Task 019 does not implement a
runtime health check, process supervisor, HTTP endpoint, or service daemon.

Fields:

- `schema_version`: string, required, non-empty.
- `service`: string, required, non-empty.
- `status`: string enum, required. Allowed values: `ok`, `degraded`, `starting`, `stopping`, `error`.
- `version`: string, required, non-empty.
- `uptime_seconds`: number, required, non-negative. In a future runtime, this is seconds since the reporting service started.
- `dependencies`: object, required, may be empty. No nested dependency-status schema is listed in `docs/CONTRACT_APPROVALS.md` yet.

No timestamp field exists on `HealthCheck`. If a future service needs observed
time, that field requires an approved contract change.

Owner: service contract package.

Can read: Shell, CLI, Core, supervisor.

Can write: service being checked.

## VersionInfo

Purpose: Stable service and contract version declaration.

This contract exists now for process readiness. Task 019 does not implement a
runtime version check, process supervisor, HTTP endpoint, or service daemon.

Fields:

- `schema_version`: string, required, non-empty.
- `service`: string, required, non-empty.
- `service_version`: string, required, non-empty.
- `contract_versions`: object, required, may be empty only before runtime implementation.
- `build`: object, required, may be empty only before runtime implementation.

No timestamp field exists on `VersionInfo`. If a future service needs build time
or observed time, that value must be carried inside an approved `build` shape or
a future contract change.

Owner: service contract package.

Can read: all clients and services.

Can write: service being queried.

## VoiceWorker

Purpose: Local-only worker service boundary for voice capture, wakeword/VAD,
STT/TTS backend execution, speaker playback, model asset readiness/downloads,
heartbeat/status, and safe worker telemetry.

Contract status: listed in `docs/CONTRACT_APPROVALS.md`.

Fields are implemented as bounded Pydantic models in
`packages.voice_worker_runtime.models`:

- `VoiceWorkerConfig`: local-only worker settings, active STT/TTS/voice ids,
  wakeword, VAD, audio, and privacy defaults.
- `VoiceWorkerCommand`: explicit user-triggered command envelope for start,
  stop, pause, resume, reload-config, tests, model install/remove, backend
  switches, and active voice selection.
- `VoiceWorkerCommandResult`: command id, status, event, and safe error.
- `VoiceWorkerStatus`: lifecycle, heartbeat, active backend ids, mic/playback
  status, model assets, backend readiness, wakeword supervisor state, recent
  safe events, and worker-safe telemetry.
- `VoiceWorkerEvent`: safe lifecycle/device/wakeword/VAD/STT/TTS/playback/error
  event summary.
- `VoiceWorkerErrorEnvelope`: safe reason-coded worker error envelope.

Owner: `packages.voice_worker_runtime`.

Can read: protected Control Plane, future local service supervisor, future Shell.

Can write: VoiceWorker runtime only.

Safety rules:

- The worker is local-only and must reject remote bindings.
- No hidden auto-start, hidden recording, or remote exposure.
- Raw audio, generated audio, raw transcripts, backend internals, secrets,
  provider payloads, and tool payloads are not persisted or rendered by default.
- Worker commands that touch devices or model assets must be explicit
  user-triggered operations.
- Assistant policy, AutonomyPolicy, CapabilityRuntime approval, intent routing,
  tools, memory, provider routing, RuntimeComposition supervision, and Local API
  internals remain outside the worker.

## MemoryService

Purpose: Draft future service boundary for durable memory ingestion, lookup,
retrieval, compaction support, and safe memory projections.

Contract status: draft/no implementation. Not approved until listed in
`docs/CONTRACT_APPROVALS.md`.

Owner: memory service boundary, with memory data models remaining replaceable
behind a clean adapter.

Can read: approved memory sources, safe session refs, approved telemetry
summaries, and explicit caller context.

Can write: approved memory records, embeddings/index updates, retrieval state,
and safe memory events.

Safety rules:

- The service must not become a hidden session store or an implicit long-term
  conversation log.
- Raw provider payloads, secrets, and policy decisions are not memory content by
  default.
- Memory writes require explicit policy-approved inputs and bounded redaction
  rules.
- Memory storage, indexing, and retrieval stay behind clean ports so the Core
  and caller-facing surfaces remain replaceable.

Non-goals:

- Provider routing
- Tool execution
- Policy or permission authority
- UI, shell, desktop, or voice orchestration
- Unbounded conversation persistence

## TelemetryEventService

Purpose: Draft future service boundary for persistent event history, safe
trace/event ingestion, indexed readback, and audit-friendly telemetry storage.

Contract status: draft/no implementation. Not approved until listed in
`docs/CONTRACT_APPROVALS.md`.

Owner: telemetry event service boundary, with event storage and query adapters
kept replaceable behind a clean port.

Can read: safe trace events, approved lifecycle events, and explicit read
queries.

Can write: structured telemetry events, event-history indexes, and retention or
rollup state.

Safety rules:

- The service must store only safe, redacted, structured event data.
- Raw provider payloads, secrets, and private user content are not telemetry
  content by default.
- Event history must preserve traceability without becoming a general data lake
  for product state.
- Write paths remain bounded and explicit; no hidden background ingestion from
  unrelated modules.

Non-goals:

- General application storage
- Policy or permission authority
- Provider execution
- Memory semantics
- UI, shell, desktop, or voice orchestration

## PolicyPermissionService

Purpose: Draft future service boundary for policy evaluation, permission
decisions, approval state, and safe runtime policy projections.

Contract status: draft/no implementation. Not approved until listed in
`docs/CONTRACT_APPROVALS.md`.

Owner: policy and permission service boundary, with decision engines and policy
stores kept replaceable behind clean adapters.

Can read: policy rules, requested actions, caller identity/context, risk
signals, and approved runtime metadata.

Can write: permission decisions, approval records, policy snapshots, and safe
decision events.

Safety rules:

- The service must remain the authority for policy and permission decisions
  without leaking implementation-specific state into callers.
- Decision outputs must be explicit, auditable, and redacted where needed.
- The service must not execute tools, mutate memory, or perform provider work.
- Policy evaluation and approval flows must stay isolated from UI and transport
  concerns.

Non-goals:

- Intent inference
- Provider routing or provider execution
- Tool execution
- Memory storage
- Telemetry persistence
- UI, shell, desktop, or voice orchestration

## AssistantStateEvent

Purpose: Safe loopback state event emitted by the Core turn loop and consumed by
a future desktop Shell status pill and waveform overlay.  `audio_level` is a
derived RMS scalar (0.0–1.0) only; no raw audio, transcript, or sensitive payload
is retained or transmitted.

Contract status: draft/implementation pending final contract approval.  Schema
version `0.1.1-draft`.

Fields:

- `schema_version`: string, required, non-empty.
- `ts`: string, required, ISO 8601 UTC timestamp.
- `status`: `AssistantStatusKind` enum, required.  Allowed values: `idle`,
  `listening`, `thinking`, `working`, `using_tools`, `mcp`, `skills`,
  `searching_web`, `talking`, `asking`, `needs_approval`.
- `detail`: string, required, may be empty.  Short, safe, human-readable
  context.
- `audio_level`: float, required, 0.0–1.0.  Derived RMS scalar; never raw PCM.
- `session_ref`: string or null, required, nullable.
- `trace_id`: string or null, required, nullable.
- `raw_audio_persisted`: `Literal[False]`, required, always `false`.

Owner: `packages.contracts.state_event`.

Can read: Shell, Control Plane API (loopback SSE stream), tests.

Can write: Core turn loop (via state bus), future VoiceWorker safe projection.

Safety rules:

- `audio_level` is a bounded derived scalar only; raw PCM, raw audio data, raw
  transcripts, and secrets must never appear in any state event field.
- `raw_audio_persisted` must remain `false` at all times.
- The state bus is in-process and loopback-only; no remote serialisation of raw
  fields is permitted.

## Foundation Surface Contracts

Some newer Marvex packages are bounded implementation foundations rather than public JSON contracts. Their existence does not broaden the provider-foundation contracts above and does not approve product expansion.

Classified bounded foundations are tracked in `docs/GOVERNANCE_CLASSIFICATION.md`. Existing code is not approval. Future work is allowed only when supported by the current goal spec, `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and relevant architecture docs.

Provider-foundation contracts must not be silently repurposed as assistant-turn, tool, memory, MCP, browser, marketplace, control-plane, voice, desktop, shell/orb, proactive, or vision product contracts.
