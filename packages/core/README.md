# Core Package

Status: minimal Provider Foundation implementation.

Ownership: Core runtime boundary.

Responsibility: Turn lifecycle orchestration through approved contracts and
ports. Current behavior is limited to constructing provider requests, invoking
an injected `ProviderPort`, emitting telemetry lifecycle events, and returning
contract-compatible turn output.

Assistant-runtime provider-stage wiring skeleton:

- `orchestration/assistant_provider_stage.py` is an internal foundation seam.
- It accepts an approved `AssistantTurnInput`, a caller-injected neutral
  send-capable provider, explicit provider options, and an optional telemetry
  sink.
- It delegates provider-stage work to
  `packages.assistant_runtime.provider_stage.run_provider_stage_turn(...)`.
- It is not exported from `packages.core.orchestration`, not used by
  `TurnOrchestrator`, and not wired into CLI, services, APIs, ProviderRuntime,
  adapters, or product flow.
- Task 107 adds only an explicit CLI/dev fake-provider caller for this seam; the
  normal Core `TurnOrchestrator` path remains unchanged.

Forbidden responsibilities:

- Provider-specific logic.
- Provider payload construction outside approved provider contracts.
- HTTP calls to providers.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Hidden global state.

Dependency direction:

- May depend on approved contracts, ports, and telemetry sink contracts.
- Must not depend on adapters, CLI, services, or future workers.
