# Core Package

Status: CoreService lifecycle envelope plus minimal Provider Foundation
implementation.

Ownership: Core runtime boundary.

Responsibility: Turn lifecycle orchestration through approved contracts and
ports. Current behavior is limited to constructing provider requests, invoking
an injected `ProviderPort`, emitting telemetry lifecycle events, and returning
contract-compatible turn output.

CoreService closure:

- `service.py` owns the approved CoreService lifecycle envelope.
- It exposes explicit `start()`, `shutdown()`, `get_health()`,
  `get_version()`, and `submit_turn(...)` methods.
- Health/version use the approved `HealthCheck` and `VersionInfo` contracts
  directly without importing ProcessRuntime.
- Turn submission accepts approved `AssistantTurnInput` and returns approved
  `AssistantTurnResult`.
- Execution is through an injected `CoreTurnExecutorPort` only. CoreService does
  not construct providers, select runtimes, import Local API, import
  RuntimeComposition, import adapters, or own assistant stage internals.
- Unavailable lifecycle state, executor exceptions, and executor identity
  mismatches return safe `ErrorEnvelope` results.

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
- Tasks 107 and 109 add only an explicit CLI fake-provider foundation caller for
  this seam; the normal Core `TurnOrchestrator` path remains unchanged.
- Task 110 decides that real ProviderRuntime-backed provider composition must
  live in a future separate runtime composition/factory layer, not in Core.
- Task 111 adds `packages.runtime_composition` as a fake-provider-only bridge
  proof that calls this helper from outside Core. Core still does not import the
  bridge, ProviderRuntime, adapters, or CLI.
- Task 112 wires the CLI foundation mode to RuntimeComposition. Core remains a
  callee only and still does not import RuntimeComposition.
- Task 113 adds a RuntimeComposition real-provider proof. Core remains a callee
  through `run_assistant_provider_stage_turn(...)` and does not import
  ProviderRuntime or RuntimeComposition.
- Task 114 exposes that proof through an explicit non-default CLI mode. Core
  remains a callee only and still does not import ProviderRuntime,
  RuntimeComposition, adapters, or CLI.
- Task 115 documents live-smoke and failure expectations for that CLI proof
  mode. Core behavior is unchanged; failure handling remains the existing
  deterministic provider-stage mapping.
- Task 120 decides the future local API `/v1/turns` contract should use the
  approved assistant-envelope result shape, but the API must not call Core
  directly. Core remains a callee behind RuntimeComposition-owned composition
  and an injected local API turn handler.
- Task 130 decides that a future LM Studio Responses local API mode may call
  this Core helper only through RuntimeComposition-owned handler composition.
  Core must not import Local API, RuntimeComposition, ProviderRuntime, adapters,
  or provider-specific policy for that mode.
- Task 131 implements that local API mode without changing Core behavior.
- Task 133 keeps provider-token configuration out of Core. Core continues to
  receive an already constructed provider through the existing helper and must
  not read, store, log, route, or validate provider credentials.

Forbidden responsibilities:

- Provider-specific logic.
- Provider payload construction outside approved provider contracts.
- HTTP calls to providers.
- HTTP request parsing, local bearer auth enforcement, or local API endpoint
  ownership.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Hidden global state.
- Provider-token or provider-credential handling.

Dependency direction:

- May depend on approved contracts, ports, and telemetry sink contracts.
- Must not depend on adapters, CLI, services, or future workers.
- Must not depend on ProviderRuntime for the assistant-runtime provider-stage
  production bridge.
