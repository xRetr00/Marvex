# Runtime Composition Package

Status: narrow runtime composition bridge proof layer.

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
- The official CLI foundation mode calls this bridge; the compatibility alias
  reaches the same path.
- `assistant_provider_bridge.py` also exposes
  `run_lmstudio_responses_assistant_bridge(...)` as the first explicit
  real-provider-backed AssistantRuntime proof path.
- The LM Studio Responses proof creates only the approved
  `lmstudio_responses` provider through ProviderRuntime and uses the same Core
  helper / AssistantRuntime provider-stage path. Automated tests stub
  ProviderRuntime creation, so no live LM Studio server is required for CI.
- The explicit CLI proof mode `--assistant-runtime-lmstudio-responses` calls
  this bridge. It is non-default, manual-provider-backed proof behavior only.
- Task 115 documents live-smoke expectations and failure policy for the CLI
  proof mode. RuntimeComposition still only composes the approved provider and
  Core helper; it does not probe provider health, route providers, retry/fallback,
  manage sessions/history, select models, own API-key policy, or format CLI
  output.
- Task 116 records a successful manual CLI smoke against LM Studio. The bridge
  remains composition-only; the CLI-owned print hardening does not change
  RuntimeComposition behavior.
- `provider_foundation_bridge.py` exposes `run_provider_foundation_turn(...)`
  for the existing CLI provider-foundation turn path so CLI does not construct
  providers directly. This preserves existing default CLI behavior and does not
  promote AssistantRuntime real-provider behavior.
- The AssistantRuntime bridge remains proof coverage. It is not default CLI
  behavior, service/API behavior, or product behavior.
- Task 120 decides that future protected local API `POST /v1/turns` execution
  must still keep RuntimeComposition as the provider/Core/AssistantRuntime
  composition owner. `packages.local_api` must not import this package directly;
  a future endpoint implementation should receive an injected turn handler at
  the HTTP boundary. The first approved target behind that handler is
  fake-provider only. LM Studio Responses over the local API remains blocked
  until a separate service/API promotion task.

Forbidden responsibilities:

- Concrete provider adapter imports.
- Provider routing, retry/fallback policy, model selection, API-key policy, or
  provider health selection.
- Session storage, conversation history, hidden global state, service lifecycle,
  CLI behavior, tools, memory, UI, voice, desktop, vision, or proactive behavior.
- Telemetry persistence or sanitizer policy ownership.

Dependency direction:

- May import approved contracts, telemetry sink contracts, ProviderRuntime
  factory/config, the Core assistant-provider-stage helper, and the existing
  Core provider-foundation orchestrator.
- Must not import concrete provider adapters, AssistantRuntime directly, ports,
  CLI apps, or services.
- Core, AssistantRuntime, and ProviderRuntime must not import this package.
- CLI may import only the approved root functions
  `run_fake_provider_assistant_bridge(...)`,
  `run_lmstudio_responses_assistant_bridge(...)`, and
  `run_provider_foundation_turn(...)`.
