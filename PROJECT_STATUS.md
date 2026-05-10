# Project Status

current_phase: structured_output_fallback_design_spec

implementation_status: structured_output_fallback_design_spec_complete_implementation_blocked

accepted_docs: true

completed_foundation:

- contracts
- ProviderPort
- FakeProvider
- LiteLLMProvider
- LMStudioResponsesProvider
- ProviderRuntime
- TurnOrchestrator
- minimal telemetry lifecycle
- CLI vertical slice
- manual provider smoke harness
- validation gates
- assistant envelope contract models
- assistant_runtime foundation helpers
- provider_structured_output no-network validation skeleton
- fake adapter-shaped structured result pressure tests

completed_process_readiness:

- Task 019 Health and Version Contract Slice completed
- Task 020 ProcessRuntime local health/version provider completed
- Task 021 ProcessRuntime boundary gate completed
- Task 026 HTTP Endpoint Contract Planning completed
- Task 028 CLI Health/Version Commands completed

completed_governance_gates:

- Task 018 Provider Foundation Governance Cleanup
- Task 021 ProcessRuntime Boundary Validation Gate
- Task 022 Git Workflow Governance completed
- Task 023 Process Readiness Architecture Audit completed
- Task 024 Status and README Drift Cleanup completed
- Task 031 Agent Context Architecture governance completed
- Task 032 Agent Context Budget Validation Gate completed
- Task 042 Assistant Turn Spine Governance completed
- Task 043B Assistant Turn Contract Map Governance completed
- Task 044B Runtime Ownership Governance completed
- Task 045B Library Research Matrix Governance completed
- Task 046B Assistant Turn Envelope Governance completed
- Task 047 Assistant Turn Envelope Schema Draft completed
- Task 050 Assistant Envelope Contract Semantic Revision completed
- Task 052 Assistant Envelope Schema Hardening completed
- Task 054 Assistant Envelope Approval Cleanup completed
- Task 056 Assistant Envelope Contract Approval completed
- Task 057 Assistant Envelope Contract Models accepted
- Task 061 Project Status Alignment completed
- Task 077 Project Status Alignment After Provider Structured-Output Skeleton completed
- Task 078 Provider-Native Structured Output Compatibility Spike Spec completed
- Task 079 LM Studio Responses Structured Output Manual Spike Harness completed
- Task 080 LM Studio Responses Structured Output Manual Spike Observed
- Task 081 Structured Output Fallback Decision After LM Studio Spike completed
- Task 082 Structured Output Fallback Design Spec completed

current_governance_gate:

Task 082 Structured Output Fallback Design Spec

allowed_current_work:

- documentation
- templates
- project status updates
- Git workflow governance
- approved task slices only
- narrow assistant-runtime foundation slices with a separate approved task spec
- provider-native structured-output compatibility spike/spec work after Task 077
  status alignment
- provider-native structured-output compatibility spike execution only after a
  separate approved task spec
- manual LM Studio structured-output spike harness execution when explicitly
  requested and local LM Studio/model are available
- follow-up provider-native compatibility planning based on Task 080
  observations
- fallback design planning based on raw provider text, strict Pydantic
  validation, deterministic failure mapping, and sanitized error output
- fallback implementation task only after separate approval with explicit
  contracts, tests, validation commands, and boundary constraints

forbidden_current_work:

- unapproved product behavior changes
- runtime behavior changes
- endpoint behavior changes
- provider behavior changes
- CLI behavior changes
- telemetry runtime behavior changes
- contract model behavior changes
- assistant-runtime integration without a separate approved task spec
- provider bridge behavior without a separate approved task spec
- real provider-native structured-output bridge behavior without a separate
  approved compatibility spike/spec
- provider-native structured-output implementation before better provider
  evidence or an accepted fallback design
- fallback behavior implementation before a separate approved implementation
  task
- ProviderRuntime structured-output behavior changes without a separate
  approved task spec
- Core or CLI assistant-runtime provider integration without a separate approved
  task spec
- service contract implementation without separate approval
- validation script changes outside an approved validation task
- UI implementation
- tools
- memory
- voice
- desktop context
- proactive behavior
- vision

status_rule:

Provider Foundation completed. Task 018 Provider Foundation Governance Cleanup
aligned documentation, dependency governance, schema-version policy, and
validation with the completed foundation before starting the next subsystem.

Process Readiness has started. Process Readiness contracts completed through
Task 019. ProcessRuntime local provider completed through Task 020.
ProcessRuntime boundary gate completed through Task 021.

Git workflow governance completed through Task 022. It establishes the default
main-first task flow, branch approval requirement, and commit/push discipline for
future Marvex tasks.

Task 023 audit completed. It found README/status drift after Process Readiness
and Git workflow governance work.

Task 024 is the current governance cleanup. It aligns README.md,
PROJECT_STATUS.md, and project-status validation with the post-Task-022 state.

Task 026 is the current governance planning slice. It documents future
localhost-only HTTP endpoint contracts for health/version responses without
implementing HTTP runtime behavior, service mode, daemon behavior, subprocess
runtime, CLI integration, Core integration, or dependency additions.

Task 028 adds local CLI health/version commands using ProcessRuntime contract
objects from explicit in-memory config. It does not add HTTP endpoints, service
mode, daemon behavior, subprocess runtime, provider health checks, config
files, environment reads, Core integration, or ProviderRuntime integration.

Task 031 adds agent context architecture docs and mandatory read-budget rules.
It does not change product behavior, runtime behavior, CLI behavior, provider
behavior, or validation scripts.

Task 032 adds a lightweight validation gate for agent context architecture docs
and task-spec Context Pack fields. It does not change product behavior, runtime
behavior, CLI behavior, provider behavior, or actual agent tool execution.

Task 042 persists the Assistant Turn Spine governance rule that the provider turn
is not the assistant turn. It adds governance documentation and a validation gate
only. It does not change product behavior, runtime behavior, CLI behavior,
provider behavior, Core orchestration, service runtime behavior, contracts, tools,
memory, voice, desktop context, UI, proactive behavior, or telemetry persistence.

Task 043B persists the Assistant Turn Contract Map governance rule that current
approved contracts are provider-foundation contracts, not assistant-turn
contracts. It adds governance documentation and a validation gate only. It does
not create Pydantic models, approve contracts, change runtime behavior, add
dependencies, or implement assistant-level modules.

Task 044B persists the runtime ownership decision that Core owns the assistant
lifecycle envelope, AssistantTurnRuntime owns assistant stage dispatch, subsystem
runtimes own domain selection/dispatch/lifecycle/execution, adapters own external
protocols, and ports remain minimal contracts only. It adds governance
documentation and a validation gate only. It does not implement runtime code,
contracts, dependencies, service placeholders, or product behavior.

Task 045B persists the ecosystem-wide library research matrix from Task 045A.
It records the current approved provider-foundation library posture, broader
discovery sources, future decision-record areas, adapter-only/pattern-only
candidates, no-framework-takeover rules, and thin-glue limits. It adds
governance documentation and a validation gate only. It does not approve
libraries, add dependencies, implement runtime code, or change product behavior.

Task 046B persists the smallest assistant turn envelope direction from Task 046.
It records `InputEvent`, `AssistantTurnInput`, `AssistantTurnResult`, and
`AssistantFinalResponse` as the planned assistant-level envelope above provider
foundation. It protects `TurnInput`, `TurnOutput`, `FinalResponse`,
`ProviderRequest`, and `ProviderResponse` from being silently repurposed as
assistant-turn contracts. It adds governance documentation and a validation gate
only. It does not create Pydantic models, approve contracts, implement runtime
code, add dependencies, or change product behavior.

Task 047 drafts documentation-only schemas for `InputEvent`,
`AssistantTurnInput`, `AssistantTurnResult`, and `AssistantFinalResponse`.
It adds draft/no approval rows and a validation gate that keeps implementation
blocked while approval is draft/no. It does not create Pydantic models, approve
contracts for implementation, change runtime behavior, add dependencies, or
change provider/CLI/Core behavior.

Task 050 tightens the documentation-only assistant envelope contract semantics.
It adds closed draft assistant-envelope enums, exact text-first payload/content
carrier rules, hybrid reference strategy, minimal stage summary and provider ref
shapes, seed-only `policy_context`, candidate-only memory write hint semantics,
and stricter validation. Contracts remain draft/no. It does not create Pydantic
models, approve contracts, change runtime behavior, add dependencies, or change
provider/CLI/Core behavior.

Task 052 hardens the documentation-only assistant envelope drafts with concrete
reference formats, explicit nested `privacy` and `policy_context` shapes, closed
stage/provider status values, assistant envelope schema-version notes, and JSON
example parsing in validation. Contracts remain draft/no. It does not create
Pydantic models, approve contracts, change runtime behavior, add dependencies,
or change provider/CLI/Core behavior.

Task 054 resolves the final documentation cleanup found by Task 053. It makes
`privacy` and `policy_context` wording consistent with their required minimal
shapes, normalizes provider turn references to the typed `ref_type` / `ref_id`
strategy, and keeps stage/provider status values aligned. Contracts remain
draft/no. It does not create Pydantic models, approve contracts, change runtime
behavior, add dependencies, or change provider/CLI/Core behavior.

Task 056 approves the four assistant envelope contracts: `InputEvent`,
`AssistantTurnInput`, `AssistantTurnResult`, and `AssistantFinalResponse`.
Approval permits future implementation tasks to use these contracts, but this
task does not create Pydantic models, change runtime behavior, add dependencies,
or change provider/CLI/Core behavior. The validation gate now checks approved
rows, JSON examples, semantic hardening phrases, provider-foundation separation,
and absence of implementation classes.

Task 057 implements and accepts the four approved assistant envelope contract
models: `InputEvent`, `AssistantTurnInput`, `AssistantTurnResult`, and
`AssistantFinalResponse`. The implementation is contracts-only and keeps the
provider foundation separate from the assistant envelope. It does not implement
`AssistantTurnRuntime`, provider bridge behavior, service contracts, memory,
tools, voice, UI, desktop agent behavior, proactive behavior, HTTP/IPC/service
daemon behavior, or process runtime behavior.

Task 061 aligns project status after assistant envelope acceptance. Latest
recorded validation passed with `python -m pytest -q` reporting 221 passed and
1 skipped, and `python scripts/run_all_checks.py` reporting all validation
checks passed.

Task 070 adds the no-network provider structured-output adapter skeleton using
existing Pydantic validation and fake/result-shaped payloads. It does not call
providers, render prompts, add dependencies, change ProviderRuntime, change
Core, change CLI, or implement provider-native structured-output execution.

Task 071 adds provider structured-output mapping around
`validate_structured_result(...)` and approved Marvex contracts. It remains
no-network validation and does not implement a real provider bridge.

Task 073 records the provider structured-output handoff decision. The handoff
shape remains a README/test fixture, not a formal Marvex contract. It carries
`trace_id` and `structured_payload` only, and it must not freeze provider
response identifiers, runtime references, refusal semantics, incomplete
semantics, retry policy, or provider adapter behavior before real provider
pressure exists.

Task 074 adds a fake provider structured-output bridge path for no-network
adapter-shaped data. It pressure-tests mapping boundaries without changing
ProviderRuntime, provider adapters, Core, AssistantTurnRuntime, CLI, services,
contracts, or dependencies.

Task 075 pressure-tests fake structured results through the provider structured
output boundary. Task 075 is completed, committed, and pushed on `main` at
commit `8d8b1dd Task 075 pressure test fake structured results`.

Current boundary state after Task 075:

- `assistant_runtime` remains a thin no-provider assistant-envelope helper
  layer. It normalizes input, builds `AssistantTurnInput`, assembles
  deterministic no-provider `AssistantTurnResult` objects, and contains only a
  minimal deterministic `AssistantTurnRuntime` skeleton.
- `provider_structured_output` remains a no-network Pydantic validation and fake
  pressure-helper layer. It validates already-available structured payloads into
  Marvex-owned contracts and returns validated models or `ErrorEnvelope`.
- No real provider-native structured-output bridge exists yet.
- No provider adapter emits real provider-native structured-output payloads yet.
- No ProviderRuntime structured-output behavior exists yet.
- No Core or CLI assistant-runtime provider integration exists yet.
- No formal structured-output handoff contract exists yet.
- Refusal and incomplete semantics remain future work.
- Tools, memory, voice, UI, desktop agent behavior, proactive behavior,
  HTTP/IPC/service daemon behavior, and process-worker behavior remain
  future-only unless separately approved.

Task 077 aligns project status after the provider structured-output skeleton and
fake adapter-shaped pressure tests. Latest recorded validation passed with
`python -m pytest -q` reporting 281 passed and 1 skipped, and
`python scripts/run_all_checks.py` reporting all validation checks passed.

Task 078 updates the provider structured-output spike decision so the next real
compatibility spike is explicit before implementation. It selects the existing
LM Studio Responses provider path through the pinned OpenAI Python SDK as the
first provider-native structured-output compatibility target, defines the
provider behaviors that must be observed, defines sanitized report outputs, and
keeps the task planning/spec-only. Task 078 does not run the real spike, does
not implement provider-native structured output, does not add dependencies, and
does not change ProviderRuntime, provider adapters, Core, CLI,
AssistantTurnRuntime, services, ports, or product/runtime behavior.

Task 079 adds a manual, opt-in LM Studio Responses structured-output observation
harness at `scripts/spike_lmstudio_structured_output.py`. The harness uses the
pinned `openai==2.24.0` client surface, targets `http://localhost:1234/v1` by
default, requires an explicit `--model`, generates a fresh `trace_id` per run,
prints sanitized observation blocks only, and remains excluded from
`scripts/run_all_checks.py`. Task 079 does not run the real spike by default,
does not implement provider-native structured output, does not add dependencies,
does not persist trace logs, and does not change ProviderRuntime, provider
adapters, Core, CLI, AssistantTurnRuntime, services, ports, or product/runtime
behavior.

Task 080 runs the manual LM Studio Responses structured-output observation
harness against local model `qwen3.5-0.8b`. The sanitized observations show that
`responses.parse` did not return a parsed structured object for valid,
refusal-like, or incomplete/length-like pressure cases. The invalid-schema
pressure case completed with raw fallback text rather than a provider schema
rejection. This is partial/unsupported provider-native structured-output
behavior for the tested model/path, not an implementation-ready bridge result.
Task 080 does not implement provider-native structured output, does not add
dependencies, does not promote a handoff contract, and does not change
ProviderRuntime, provider adapters, Core, CLI, AssistantTurnRuntime, services,
ports, or product/runtime behavior.

next_allowed_work_after_task_080:

The next allowed direction is follow-up provider-native compatibility planning:
either test a different loaded LM Studio model or narrower OpenAI-compatible
request shape, or document a fallback plan that treats LM Studio structured
output as raw provider text plus explicit Pydantic validation and deterministic
error mapping. Any follow-up must keep provider specifics behind
adapter/provider-runtime ownership and must not silently expand Core, CLI,
AssistantTurnRuntime, services, tools, memory, voice, UI, desktop agent
behavior, proactive behavior, HTTP/IPC/service daemon behavior, or process
runtime behavior.

The compatibility spike must report whether provider-native structured outputs
plus Pydantic validation are sufficient before adding a dependency such as
Promptify, Instructor, Outlines, Guidance, Pydantic AI, LangGraph, or any other
structured-output framework. It must not promote the handoff fixture into a
formal contract until refusal, incomplete, fallback, error, and trace handling
are understood from observed provider behavior.

Task 081 records the post-Task-080 decision. The tested path was LM Studio
Responses at `http://localhost:1234/v1` through pinned `openai==2.24.0` using
model `qwen3.5-0.8b`. `responses.parse` was not usable enough on that
path/model, parsed structured objects were not reliably returned, raw fallback
appeared only in the invalid-schema pressure case, and refusal/incomplete
semantics remain unresolved. Task 081 keeps provider-native structured-output
implementation blocked pending either better provider evidence or an accepted
fallback design. It does not implement provider-native structured output, add
dependencies, create parser/retry behavior, promote a handoff contract, or
change ProviderRuntime, provider adapters, Core, CLI, AssistantTurnRuntime,
services, ports, or product/runtime behavior.

Latest recorded validation after Task 081 passed with `python -m pytest -q`
reporting 287 passed and 1 skipped, `python scripts/check_project_status.py`
reporting PASS, and `python scripts/run_all_checks.py` required as the final
aggregate gate for completion.

next_allowed_work_after_task_081:

The next allowed directions are alternatives only: run a second manual spike
with a stronger or different loaded LM Studio model, try a narrower
OpenAI-compatible request shape if the installed client/server support one, or
design a fallback path around raw provider text, strict Pydantic validation,
deterministic validation failure mapping, sanitized error output, and no custom
JSON repair parser unless separately justified. Implementation remains blocked
until stable parsed-object behavior is observed or an explicit fallback decision
is accepted with deterministic invalid-output semantics, documented
refusal/incomplete/error mapping, clear `trace_id` propagation behavior, and
passing validation gates.

Task 082 designs the fallback path without implementing it. The design defines
fallback input as raw provider output text, an explicit schema or Marvex-owned
Pydantic contract target, and explicit `trace_id` / `turn_id` context. It
requires strict JSON handling only when the full output is already valid JSON or
the provider explicitly returns a JSON field, Pydantic validation through
Marvex-owned contracts, deterministic invalid-output mapping, sanitized errors,
and preserved trace context. It defines conservative output states:
`valid_structured_result`, `invalid_structured_output`, `provider_error`,
`provider_timeout`, `refusal_unresolved_or_provider_specific`, and
`incomplete_unresolved_or_provider_specific`. It explicitly forbids custom JSON
repair, heuristic brace scraping, silent retries, hidden prompt mutation,
handoff contract promotion, and raw provider output in telemetry/logs by
default. Task 082 does not implement fallback behavior, add dependencies, create
parser/retry behavior, promote a handoff contract, or change ProviderRuntime,
provider adapters, Core, CLI, AssistantTurnRuntime, services, ports, or
product/runtime behavior.

Latest recorded validation after Task 082 passed with
`python scripts/check_project_status.py` reporting PASS and
`python scripts/run_all_checks.py` reporting all validation checks passed.

next_allowed_work_after_task_082:

Structured-output implementation remains blocked until this fallback design is
accepted by a separate implementation task with explicit allowed files,
contracts or typed result shape, tests, validation commands, and boundary
constraints. Future work may either run another manual provider-native model
spike or implement a small adapter-local fallback mapper outside Core,
ProviderRuntime, AssistantTurnRuntime, CLI, services, and ports if separately
approved.
