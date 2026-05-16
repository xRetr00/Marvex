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

## Local Service Startup Token Rule

Future local bearer token generation belongs to the service runner/startup
boundary for the running process. Request handlers, Core, ProviderRuntime,
AssistantRuntime, RuntimeComposition bridge helpers, provider adapters, and CLI
proof commands must not generate or own that token.

Startup may report the loopback URL, token presence, and an approved local
discovery path or explicit config instructions. Startup must not print the raw
token value by default.

Any future discovery file must be local-user scoped, describe only loopback
connection metadata, and must not expose remote interfaces. Writing discovery
files, token storage, daemon lifecycle, supervisor behavior, and restart policy
remain blocked until separate implementation tasks approve them.

Task 138 adds a startup object foundation only. It may describe future discovery
metadata and explicit shutdown semantics, but it must not write files, start a
daemon loop, enable auto-restart, or start a supervisor.

Task 139 adds only a bounded Local API service-runner startup proof around the
existing Local API runner. It may inject the generated local token into that
runner and print safe metadata, but it must not write discovery files, print raw
token values, start supervision, add auto-restart, or become a daemon lifecycle
manager.
