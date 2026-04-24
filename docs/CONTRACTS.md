# Contracts

All contracts are JSON-compatible. Product code must not invent private shapes for the same data.

Contracts are implementation-draft until approved in `docs/CONTRACT_APPROVALS.md`.

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
- `input_text`: string, required, may be empty only if an approved future input mode defines that behavior.
- `source`: string enum, required, initially `cli`.
- `metadata`: object, required, may be empty.

Owner: Core contract package.

Can read: CLI, Core, telemetry.

Can write: CLI client.

Example:

```json
{
  "schema_version": "0.1-draft",
  "trace_id": "trace-001",
  "turn_id": "turn-001",
  "input_text": "Hello",
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
  "schema_version": "0.1-draft",
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

- CLI may pass `previous_response_id` for simple sessions through `TurnInput.metadata.previous_response_id`.
- Core may copy that value into `ProviderRequest.previous_response_id` after validation.
- Core returns `provider_response_id` in `TurnOutput`.
- Core must not maintain hidden global conversation history in v1.
- A future session store must be explicit, contract-owned, and approved before implementation.

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

Fields:

- `schema_version`: string, required, non-empty.
- `service`: string, required, non-empty.
- `status`: string enum, required.
- `version`: string, required, non-empty.
- `uptime_seconds`: number, required, non-negative.
- `dependencies`: object, required, may be empty.

Owner: service contract package.

Can read: Shell, CLI, Core, supervisor.

Can write: service being checked.

## VersionInfo

Purpose: Stable service and contract version declaration.

Fields:

- `schema_version`: string, required, non-empty.
- `service`: string, required, non-empty.
- `service_version`: string, required, non-empty.
- `contract_versions`: object, required, may be empty only before implementation.
- `build`: object, required, may be empty only before implementation.

Owner: service contract package.

Can read: all clients and services.

Can write: service being queried.
