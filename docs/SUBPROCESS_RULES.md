# Subprocess Rules

Every major module must be process-ready from day one, even when implemented in-process at first.

## Required Service Surface

Each service or future worker must define:

- health check
- version response
- startup behavior
- shutdown behavior
- structured logs
- trace_id propagation
- error envelope
- contract version

## Process Isolation Rule

Future services must not require shared mutable memory with Core. Communication must happen through JSON contracts.

## Crash Rule

A worker crash must be reported as an `ErrorEnvelope`. Core state must remain valid.

## Restart Rule

Restart behavior must be explicit. No hidden automatic restart loops without telemetry events.

## Shutdown Rule

Shutdown must be graceful when possible and bounded by timeout. Forced termination must emit a trace event.

