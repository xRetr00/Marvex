# Runtime Composition Package

Status: narrow fake-provider bridge proof.

Ownership: runtime composition/factory bridge.

Responsibility: Compose already approved runtime boundaries without moving
their responsibilities into each other.

Current bridge proof:

- `assistant_provider_bridge.py` exposes
  `run_fake_provider_assistant_bridge(...)`.
- The bridge creates the approved `fake` provider through
  `packages.provider_runtime.create_provider(...)`.
- The bridge injects that provider into
  `packages.core.orchestration.assistant_provider_stage.run_assistant_provider_stage_turn(...)`.
- Core then delegates to
  `packages.assistant_runtime.provider_stage.run_provider_stage_turn(...)`.
- This is fake-provider-only proof coverage. It is not real provider-backed
  AssistantRuntime product behavior.

Forbidden responsibilities:

- Concrete provider adapter imports.
- Provider routing, retry/fallback policy, model selection, API-key policy, or
  provider health selection.
- Session storage, conversation history, hidden global state, service lifecycle,
  CLI behavior, tools, memory, UI, voice, desktop, vision, or proactive behavior.
- Telemetry persistence or sanitizer policy ownership.

Dependency direction:

- May import approved contracts, telemetry sink contracts, ProviderRuntime
  factory/config, and the Core assistant-provider-stage helper.
- Must not import concrete provider adapters, AssistantRuntime directly, ports,
  CLI apps, or services.
- Core, AssistantRuntime, ProviderRuntime, and CLI must not import this package
  until a separate explicit task approves a caller.
