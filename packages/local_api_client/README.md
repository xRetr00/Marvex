# Local API Client Package

Status: narrow future Shell/CLI connection proof helper.

Ownership: read safe local discovery metadata and make explicit loopback Local
API JSON requests for future client proof paths.

Current responsibilities:

- load token-redacted local service discovery metadata through
  `packages.local_service_startup.discovery`
- validate that metadata remains loopback-only and token-redacted
- call public `/health` and `/version` without auth headers
- call protected `/v1/turns` and `GET /v1/traces/{trace_id}` only when the
  caller supplies a local bearer token explicitly
- return status code plus JSON object bodies without storing client state beyond
  safe connection metadata

Token rule:

- discovery metadata proves that a token exists, but never carries the token
  value
- the caller must obtain the raw local bearer token through a private startup
  handoff outside the discovery file and pass it per protected call
- this package must not persist, discover, rotate, print, or cache bearer tokens

Forbidden responsibilities:

- daemon launch, auto-start, cleanup, supervision, or restart behavior
- token storage, credential lookup, provider credential handling, or environment
  reads
- session/history management, retry/fallback, provider routing, model selection,
  WebSocket/events, persistent telemetry, cross-process traces, tools, memory,
  UI, voice, desktop, vision, or proactive behavior
- importing Local API handlers, RuntimeComposition, Core, AssistantRuntime,
  ProviderRuntime, adapters, telemetry implementation modules, CLI apps, or
  services

Dependency direction:

- may use Python standard-library HTTP helpers and the safe discovery reader
- must remain a client helper, not a service lifecycle owner or product UI
