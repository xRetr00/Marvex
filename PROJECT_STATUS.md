# Project Status

current_phase: project_status_compaction_runtime_promotion_decision_pack

implementation_status: governance_status_compaction_only_runtime_behavior_unchanged

accepted_docs: true

current_governance_gate:

Task 108 Project Status Compaction and Next Runtime Promotion Decision Pack

## Validation Baseline

Latest full validation baseline from Task 107:

- `python -m pytest tests\cli tests\core tests\assistant_runtime tests\provider_structured_output tests\telemetry tests\provider_runtime tests\integration -q` -> 383 passed
- `python -m pytest -q` -> 611 passed, 1 skipped
- `python scripts\run_all_checks.py` -> PASS all validation checks passed

Task 108 is documentation/governance only. It does not implement or promote
runtime, CLI, provider, service, API, telemetry, contract, port, or product
behavior.

## Current Foundation Capabilities

Provider Foundation completed:

- approved Pydantic provider-foundation contracts, schema generation, and schema
  version policy
- `ProviderPort` as the minimal provider boundary
- deterministic fake provider plus LiteLLM and LM Studio Responses adapters
- `ProviderRuntime` as the only approved provider construction boundary
- Core `TurnOrchestrator` for the existing provider-foundation turn path
- one-shot CLI provider path and manual provider smoke harness
- minimal telemetry lifecycle through `TelemetrySink`, `NoopTelemetrySink`, and
  `make_trace_event(...)`

Process Readiness has started:

- `HealthCheck` and `VersionInfo` contracts exist
- local `ProcessRuntime` health/version object construction exists
- ProcessRuntime boundary gate completed
- CLI health/version commands exist
- no HTTP endpoint, service daemon, subprocess runtime, or service mode exists

Assistant-runtime foundation now present:

- approved assistant-envelope models: `InputEvent`, `AssistantTurnInput`,
  `AssistantTurnResult`, and `AssistantFinalResponse`
- assistant-runtime input normalization, result assembly, no-provider runtime
  skeleton, structured-output consumption helpers, and provider-stage skeleton
- Core internal assistant-runtime provider-stage wiring skeleton
- CLI opt-in fake-provider vertical slice via
  `--assistant-runtime-provider-stage-fake`

Provider structured-output foundation now present:

- boundary-local validation and fallback result model
- adapter-local hooks for LM Studio Responses and LiteLLM
- explicit ProviderRuntime experimental structured-output adapter call path
- internal handoff draft and pressure coverage
- test-only ProviderRuntime-to-AssistantRuntime bridge proof
- no production structured-output bridge or product runtime integration

Validation gates now present:

- workspace/docs/service-placeholder/forbidden-module gates
- project status, file-size, schema-version, library-decision, and library
  research gates
- port, ProviderRuntime, ProcessRuntime, AssistantRuntime, provider structured
  output, runtime ownership, Vaxil boundary, and assistant-turn contract gates

Historical governance retained compactly: Task 024 Status and README Drift Cleanup,
Git workflow governance, assistant-turn spine/contract governance, runtime
ownership governance, and library research governance remain accepted.

## Task 102-107 Compact Milestone Summary

- Task 102 wired telemetry-owned structured-output trace safety into
  `packages.telemetry.sinks.make_trace_event(...)`.
- Task 103 added explicit AssistantRuntime structured-output consumption as an
  experimental helper.
- Task 104 proved ProviderRuntime structured-output output can be consumed by
  AssistantRuntime only through test/integration helpers.
- Task 105 added `run_provider_stage_turn(...)`, an AssistantRuntime-owned
  injected provider-stage skeleton.
- Task 106 added `run_assistant_provider_stage_turn(...)`, a Core-owned
  internal wiring skeleton that delegates to AssistantRuntime.
- Task 107 added the opt-in CLI/dev fake-provider vertical slice with
  `--assistant-runtime-provider-stage-fake`, leaving default CLI behavior
  unchanged.

## Architecture Health Notes

- The current direction is still foundation-first rather than product-first.
- Telemetry owns redaction/sanitization policy; callers use safe event
  construction instead of owning sanitizer policy.
- AssistantRuntime remains provider-agnostic and does not import Core,
  ProviderRuntime, adapters, ports, CLI, or services.
- Core has a narrow assistant-runtime provider-stage seam but the existing
  `TurnOrchestrator` provider path remains unchanged.
- CLI has one explicit dev-only assistant-runtime fake-provider path; the
  default provider CLI path remains the provider-foundation path.
- ProviderRuntime remains the only approved production provider construction
  boundary and has not been wired into the AssistantRuntime provider-stage path.
- `PROJECT_STATUS.md` is no longer a chronological task log; historical detail
  belongs in package READMEs, tests, task reports, and git history.

## Explicit Non-Goals And Blocked Work

Blocked without a separate approved task spec:

- default CLI behavior changes
- ProviderRuntime production bridge into AssistantRuntime
- real provider promotion for assistant-runtime turns
- Core normal orchestration replacement
- service/API/HTTP/WebSocket/subprocess runtime or daemon behavior
- telemetry persistence/storage/logging sinks
- contract or port promotion
- tools, memory, UI, voice, desktop, vision, proactive behavior
- sessions, hidden history, routing, retry/fallback, API keys, or model routing
- structured-output handoff promotion into a public contract

A roadmap item, package README note, status recommendation, or task number is
not implementation permission.

## Next Runtime Promotion Decision

Candidate A: promote the opt-in CLI fake path toward normal CLI foundation.

- Foundation value: high for assistant-turn plumbing and result formatting.
- Speed value: high because Tasks 105-107 already prove the fake-provider path.
- Architecture risk: medium; the main risk is accidentally turning a dev-only
  fake path into product/default behavior before provider ownership is settled.
- Unlocks: a clearer assistant-runtime CLI foundation, stable bounded output,
  and stronger Core/CLI assistant-turn regression coverage.
- Must not touch: real providers, ProviderRuntime production bridge, services,
  APIs, sessions, history, routing, retry/fallback, tools, or memory.

Candidate B: decide ProviderRuntime production bridge ownership.

- Foundation value: high for eventual real provider-backed assistant turns.
- Speed value: medium; it is mostly ownership and seam design before code.
- Architecture risk: medium-high if rushed, because ProviderRuntime,
  AssistantRuntime, Core, and provider adapters must not start importing each
  other in the wrong direction.
- Unlocks: a future bounded production provider bridge task.
- Must not touch: default CLI behavior, real provider execution behavior, ports,
  contracts, services, or product flow until the owner and call path are explicit.

Candidate C: local health/version API readiness.

- Foundation value: high for process/service readiness, but lower for the
  assistant-turn runtime chain.
- Speed value: medium because health/version contracts and local objects exist.
- Architecture risk: low-medium if kept contract-only or local-only; higher if
  it starts a server too early.
- Unlocks: future service boundary work.
- Must not touch: assistant turn orchestration, providers, CLI provider paths,
  tools, memory, UI, or product runtime behavior.

Recommendation, not permission: Candidate A is the safest next implementation
direction if the goal is runtime promotion, because it extends the already
proven fake-provider assistant-runtime path without real provider or service
ownership risk. Candidate B should precede any real provider-backed
AssistantRuntime promotion. Candidate C is valid but orthogonal to the
assistant-turn runtime chain.
