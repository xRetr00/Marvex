# Project Status

current_phase: manual_lmstudio_assistant_runtime_smoke_execution_record_pack

implementation_status: lmstudio_cli_proof_live_smoke_recorded

accepted_docs: true

current_governance_gate:

Task 116 Manual LM Studio AssistantRuntime Smoke Execution Record Pack

## Validation Baseline

Latest full validation baseline from Task 116:

- `python scripts\run_all_checks.py` -> PASS all validation checks passed
- `python -m pytest -q` -> 640 passed, 1 skipped

Task 111 adds the first separate runtime composition/factory bridge proof using
ProviderRuntime-created fake provider only. It does not change default CLI
behavior or implement real provider, service, API, telemetry storage,
session/history, routing, retry/fallback, tool, memory, or product behavior.

Task 112 wires the official CLI fake-provider AssistantRuntime foundation mode
to RuntimeComposition instead of local CLI provider composition. It also moves
existing default CLI provider-foundation composition behind RuntimeComposition
without changing default output behavior.

Task 113 adds a RuntimeComposition-only real-provider-backed AssistantRuntime
proof for `lmstudio_responses`. Automated tests stub ProviderRuntime behavior;
no live provider, CLI flag, service/API, session/history, routing,
retry/fallback, model-selection, API-key policy, tool, memory, or product
behavior is added.

Task 114 adds the explicit non-default CLI proof flag
`--assistant-runtime-lmstudio-responses`. The CLI calls RuntimeComposition only;
it does not import ProviderRuntime or adapters, create providers, own routing,
retry/fallback, sessions/history, model-selection, API-key policy, service/API,
or product behavior. Automated tests mock the bridge; live LM Studio remains
manual smoke only.

Task 115 documents the live-smoke checklist and failure policy for that explicit
CLI proof mode. It does not add automatic preflight probing, retry/fallback,
routing, sessions/history, model-selection policy, service/API behavior, or
default product behavior.

Task 116 executes and records a manual live smoke for
`--assistant-runtime-lmstudio-responses` against LM Studio with `qwen3.5-0.8b`.
The smoke succeeded with assistant response text, provider response id, trace id,
and turn id present. A Windows legacy-console Unicode print failure observed on
the first run was fixed narrowly in the CLI proof-mode result printer by
replacing unencodable characters. No default CLI behavior, preflight,
retry/fallback, routing, session/history, model-selection, service/API, or
product behavior was added.

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
- CLI now calls RuntimeComposition for both the official fake-provider
  AssistantRuntime foundation mode and the existing provider-foundation turn
  path; CLI no longer imports ProviderRuntime directly
- ProviderRuntime production bridge ownership decision: future real-provider
  AssistantRuntime composition belongs in a separate runtime composition/factory
  layer, not in CLI, Core, AssistantRuntime, ProviderRuntime, ports, or adapters
- `packages.runtime_composition.run_fake_provider_assistant_bridge(...)` proves
  that separate layer with ProviderRuntime-created fake provider only; it calls
  Core's assistant-provider-stage helper and reaches AssistantRuntime provider
  stage behavior without changing default CLI behavior
- `packages.runtime_composition.run_lmstudio_responses_assistant_bridge(...)`
  is the first explicit real-provider-backed AssistantRuntime proof path
- explicit non-default CLI proof mode via
  `--assistant-runtime-lmstudio-responses`; it calls RuntimeComposition and is
  not default, service/API, or product flow
- documented manual live-smoke checklist and bounded failure policy for LM
  Studio unavailable/model rejected, timeout-like, provider error, empty output,
  and malformed response cases
- recorded successful manual live smoke for `qwen3.5-0.8b`, with bounded output
  details and no CI/live-provider validation requirement

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

## Task 102-116 Compact Milestone Summary

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
- Task 112 wires the official CLI fake-provider foundation mode to the
  RuntimeComposition fake bridge and removes CLI-owned provider construction
  while preserving default CLI behavior.
- Task 113 adds the first RuntimeComposition real-provider proof for
  `lmstudio_responses`, with live execution left to manual provider smoke
  guidance only.
- Task 114 adds the explicit non-default CLI proof flag
  `--assistant-runtime-lmstudio-responses` for that bridge while preserving
  default CLI behavior and the fake-provider foundation mode.
- Task 115 documents manual live-smoke expectations and failure policy for that
  proof mode without adding preflight, routing, retry/fallback, sessions/history,
  model-selection, service/API, or default product behavior.
- Task 116 records a successful manual LM Studio AssistantRuntime CLI proof
  smoke and adds narrow Unicode-safe result printing for that proof-mode output.

## Architecture Health Notes

- The current direction is still foundation-first rather than product-first.
- Telemetry owns redaction/sanitization policy; callers use safe event
  construction instead of owning sanitizer policy.
- AssistantRuntime remains provider-agnostic and does not import Core,
  ProviderRuntime, adapters, ports, CLI, or services.
- Core has a narrow assistant-runtime provider-stage seam but the existing
  `TurnOrchestrator` provider path remains unchanged.
- CLI has one explicit fake-provider AssistantRuntime foundation mode and one
  explicit LM Studio Responses AssistantRuntime proof mode. Both call
  RuntimeComposition; the default provider CLI path remains the
  provider-foundation path and still does not construct providers inside CLI.
- The LM Studio Responses CLI proof has documented manual-smoke success/failure
  expectations; automated validation still does not require live LM Studio.
- The latest manual smoke for that proof path succeeded, but it remains a
  manual developer check and is not part of `run_all_checks.py`.
- ProviderRuntime remains the only approved production provider construction
  boundary and has not been wired into the AssistantRuntime provider-stage path.
- Future real-provider assistant-runtime composition should be a separate
  bridge/factory layer that imports ProviderRuntime and the Core helper while
  importing no concrete adapters and owning no routing/session/history policy.
- RuntimeComposition is now the approved CLI composition dependency for the
  existing provider-foundation path and the fake-provider AssistantRuntime
  foundation mode. Core, AssistantRuntime, and ProviderRuntime still do not
  import RuntimeComposition.
- RuntimeComposition also owns one real-provider AssistantRuntime proof function
  for `lmstudio_responses`, now reachable from an explicit CLI proof flag. It
  is not a router, session manager, retry/fallback owner, model-selection owner,
  API-key policy owner, or product orchestrator.
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

Candidate A: harden CLI-to-RuntimeComposition regression coverage.

- Foundation value: medium because Tasks 112 and 114 add approved caller paths.
- Speed value: high if limited to tests, docs, and boundary hardening.
- Architecture risk: low while fake-provider-only and default behavior remains
  unchanged.
- Unlocks: stronger confidence before real-provider bridge design.
- Must not touch: default CLI, services, APIs, real providers, sessions,
  history, routing, retry/fallback, tools, or memory.

Candidate B: decide the next real-provider bridge preflight.

- Foundation value: high for eventual real provider-backed AssistantRuntime
  promotion.
- Speed value: medium because Task 113 proves the narrow RuntimeComposition
  bridge and Task 114 exposes it through explicit CLI proof mode.
- Architecture risk: medium-high if it introduces routing, provider selection
  policy, sessions, retries, or API-key handling too early.
- Unlocks: manual smoke hardening and eventual real-provider promotion criteria.
- Must not touch: default CLI, services, APIs, sessions, history, routing,
  retry/fallback, tools, memory, or provider SDK behavior outside existing
  adapters.

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
if more confidence is needed. Candidate B is the next architecture-significant
direction, but real provider-backed AssistantRuntime promotion remains blocked
until a separate task defines live smoke expectations, preflight boundaries,
failure handling, and promotion criteria.
