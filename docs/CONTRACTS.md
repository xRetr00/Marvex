# Contracts

All contracts are JSON-compatible. Product code must not invent private shapes for the same data.

## TurnInput

Purpose: User input entering the Core turn lifecycle.

Fields:

- `schema_version`: string
- `trace_id`: string
- `turn_id`: string
- `input_text`: string
- `source`: string, initially `cli`
- `metadata`: object

Owner: Core contract package.

Can read: CLI, Core, telemetry.

Can write: CLI client.

## TurnOutput

Purpose: Complete result of a Core turn.

Fields:

- `schema_version`: string
- `trace_id`: string
- `turn_id`: string
- `final_response`: FinalResponse
- `provider_response_id`: string or null
- `events`: array of TraceEvent summaries
- `error`: ErrorEnvelope or null

Owner: Core contract package.

Can read: CLI, Shell later, telemetry.

Can write: Core only.

## FinalResponse

Purpose: User-facing final assistant response.

Fields:

- `text`: string
- `response_type`: string
- `finish_reason`: string
- `safe_for_tts`: boolean
- `metadata`: object

Owner: Core contract package.

Can read: CLI, Shell later, telemetry.

Can write: Core after provider response normalization.

## ProviderRequest

Purpose: Provider-agnostic request sent from Core to a provider adapter.

Fields:

- `schema_version`: string
- `trace_id`: string
- `turn_id`: string
- `model`: string
- `input_text`: string
- `instructions`: string or null
- `previous_response_id`: string or null
- `provider_options`: object

Owner: Provider port contract.

Can read: provider adapters, telemetry.

Can write: Core only.

## ProviderResponse

Purpose: Provider-agnostic response returned to Core.

Fields:

- `schema_version`: string
- `trace_id`: string
- `turn_id`: string
- `provider_name`: string
- `response_id`: string or null
- `output_text`: string
- `finish_reason`: string
- `usage`: object
- `raw_metadata`: object
- `error`: ErrorEnvelope or null

Owner: Provider port contract.

Can read: Core, telemetry.

Can write: provider adapter only.

## TraceEvent

Purpose: Structured lifecycle event for debugging, replay, and audit.

Fields:

- `schema_version`: string
- `trace_id`: string
- `event_id`: string
- `timestamp`: string
- `stage`: string
- `level`: string
- `message`: string
- `data`: object

Owner: telemetry package.

Can read: Core, CLI, Shell later, tests.

Can write: telemetry layer and approved emitters.

## ErrorEnvelope

Purpose: Stable error shape across services and adapters.

Fields:

- `schema_version`: string
- `trace_id`: string
- `error_id`: string
- `code`: string
- `message`: string
- `recoverable`: boolean
- `source`: string
- `details`: object

Owner: contracts package.

Can read: all modules.

Can write: module that detects the error.

## HealthCheck

Purpose: Runtime liveness and readiness status for a service.

Fields:

- `schema_version`: string
- `service`: string
- `status`: string
- `version`: string
- `uptime_seconds`: number
- `dependencies`: object

Owner: service contract package.

Can read: Shell, CLI, Core, supervisor.

Can write: service being checked.

## VersionInfo

Purpose: Stable service and contract version declaration.

Fields:

- `schema_version`: string
- `service`: string
- `service_version`: string
- `contract_versions`: object
- `build`: object

Owner: service contract package.

Can read: all clients and services.

Can write: service being queried.

