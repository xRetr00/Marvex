# Project Status

current_phase: runtime_composition_fake_provider_bridge_proof_pack

implementation_status: fake_provider_runtime_composition_bridge_proof_added_default_cli_unchanged

accepted_docs: true

current_governance_gate:

Task 111 Runtime Composition Fake Provider Bridge Proof Pack

## Validation Baseline

Latest full validation baseline from Task 111:

- `python -m pytest tests\core tests\assistant_runtime tests\provider_runtime tests\integration tests\cli tests\telemetry -q` -> 297 passed
- `python scripts\run_all_checks.py` -> PASS all validation checks passed
- `python -m pytest -q` -> 622 passed, 1 skipped

Task 111 adds the first separate runtime composition/factory bridge proof using
ProviderRuntime-created fake provider only. It does not change default CLI
behavior or implement real provider, service, API, telemetry storage,
session/history, routing, retry/fallback, tool, memory, or product behavior.

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
- official explicit CLI fake-provider foundation mode via
  `--assistant-runtime-fake-provider`; the Task 107 flag
  `--assistant-runtime-provider-stage-fake` remains a compatibility alias
- ProviderRuntime production bridge ownership decision: future real-provider
  AssistantRuntime composition belongs in a separate runtime composition/factory
  layer, not in CLI, Core, AssistantRuntime, ProviderRuntime, ports, or adapters
- `packages.runtime_composition.run_fake_provider_assistant_bridge(...)` proves
  that separate layer with ProviderRuntime-created fake provider only; it calls
  Core's assistant-provider-stage helper and reaches AssistantRuntime provider
  stage behavior without changing default CLI behavior

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
  output, runtime composition, runtime ownership, Vaxil boundary, and
  assistant-turn contract gates

Historical governance retained compactly: Task 024 Status and README Drift Cleanup,
Git workflow governance, assistant-turn spine/contract governance, runtime
ownership governance, and library research governance remain accepted.

## Task 102-111 Compact Milestone Summary

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
- Task 108 compacted this status file and recorded the next runtime promotion
  decision.
- Task 109 promoted the explicit fake-provider AssistantRuntime CLI path into
  the official foundation mode `--assistant-runtime-fake-provider` while keeping
  the Task 107 flag as a compatibility alias.
- Task 110 decides that a future separate runtime composition/factory layer
  should own production composition between ProviderRuntime and the
  Core/AssistantRuntime assistant-provider-stage path.
- Task 111 adds that first separate layer as a fake-provider-only proof with a
  dedicated runtime composition boundary gate.

## Architecture Health Notes

- The current direction is still foundation-first rather than product-first.
- Telemetry owns redaction/sanitization policy; callers use safe event
  construction instead of owning sanitizer policy.
- AssistantRuntime remains provider-agnostic and does not import Core,
  ProviderRuntime, adapters, ports, CLI, or services.
- Core has a narrow assistant-runtime provider-stage seam but the existing
  `TurnOrchestrator` provider path remains unchanged.
- CLI has one explicit fake-provider AssistantRuntime foundation mode; the
  default provider CLI path remains the provider-foundation path.
- ProviderRuntime remains the only approved production provider construction
  boundary and has not been wired into the AssistantRuntime provider-stage path.
- Future real-provider assistant-runtime composition should be a separate
  bridge/factory layer that imports ProviderRuntime and the Core helper while
  importing no concrete adapters and owning no routing/session/history policy.
- The first runtime composition bridge exists but is fake-provider-only and not
  imported by CLI, Core, AssistantRuntime, or ProviderRuntime.
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

Candidate A: harden the runtime composition fake-provider bridge proof.

- Foundation value: medium-high because Task 111 proves the selected ownership
  model but has not yet exposed a product caller.
- Speed value: high if limited to tests, docs, and boundary hardening.
- Architecture risk: low while fake-provider-only and unwired from CLI.
- Unlocks: stronger confidence before real-provider bridge design.
- Must not touch: default CLI, services, APIs, real providers, sessions,
  history, routing, retry/fallback, tools, or memory.

Candidate B: decide whether the official CLI foundation mode should call runtime composition.

- Foundation value: medium for aligning the dev surface with the new bridge.
- Speed value: medium because default CLI behavior must remain unchanged.
- Architecture risk: medium; CLI must not become the production bridge owner.
- Unlocks: one explicit CLI path through the same composition layer.
- Must not touch: real providers, ProviderRuntime bridge, services, APIs,
  sessions, history, routing, retry/fallback, tools, or memory.

Candidate C: local health/version API readiness.

- Foundation value: high for process/service readiness, but lower for the
  assistant-turn runtime chain.
- Speed value: medium because health/version contracts and local objects exist.
- Architecture risk: low-medium if kept contract-only or local-only; higher if
  it starts a server too early.
- Unlocks: future service boundary work.
- Must not touch: assistant turn orchestration, providers, CLI provider paths,
  tools, memory, UI, or product runtime behavior.

Recommendation, not permission: Candidate A is the safest immediate follow-up
if more confidence is needed. Candidate B is reasonable only as a separate
explicit opt-in task and must keep the default CLI path unchanged. Real
provider-backed AssistantRuntime promotion remains blocked until the fake bridge
has a stronger caller and boundary story.
