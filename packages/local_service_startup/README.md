# Local Service Startup Package

Status: startup foundation only.

Ownership: future local service runner/startup boundary for Local API startup
metadata and local bearer token creation.

Current responsibilities:

- generate a high-entropy local bearer token for a future Local API service
  runner
- build safe public startup metadata that reports token presence only
- define explicit startup/shutdown semantics as object-level state
- represent future discovery mode metadata without writing discovery files
- run a narrow Local API service-runner startup proof that injects the generated
  token into the existing Local API runner and prints safe public metadata only

Forbidden responsibilities:

- daemon loops, background service management, or auto-restart behavior
- discovery file writes or token storage
- Local API HTTP request parsing or handler behavior
- Local API handler composition or HTTP behavior beyond calling the existing
  runner with generated startup config
- RuntimeComposition provider/Core/AssistantRuntime handler composition
- Core orchestration
- ProviderRuntime provider construction or provider credentials
- persistent telemetry, WebSocket/events, sessions/history, routing,
  retry/fallback, model selection, tools, memory, UI, voice, desktop, vision, or
  proactive behavior

Dependency direction:

- may use Python standard-library startup helpers
- must not be imported by Core, ProviderRuntime, or Local API handlers
- `local_api_service_runner.py` may import the existing Local API runner/config
  only for the approved startup proof; it must not own HTTP parsing, auth
  validation internals, handler composition, trace storage, or service daemon
  behavior
