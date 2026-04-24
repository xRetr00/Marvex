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

## Forbidden

- Free-form print debugging as the only diagnostic trail.
- Silent retries.
- Swallowed exceptions.
- Logs without trace IDs.

