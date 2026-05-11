# Project Status

current_phase: provider_runtime_structured_output_exposure_decision

implementation_status: provider_runtime_exposure_decision_complete_runtime_exposure_blocked

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
- provider_structured_output fallback result model and deterministic mapping helpers
- frontend boundary planning document
- provider_structured_output fallback validation mapper
- provider_structured_output adapter-local fallback usage spike
- LM Studio and LiteLLM adapter-local structured-output hooks
- provider runtime structured-output exposure decision only

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
- Task 083 Structured Output Fallback Result Shape Spec completed
- Task 084 Structured Output Fallback Result Model completed
- Task 085 Frontend Boundary And UI Contract Planning completed
- Task 086 Structured Output Fallback Validation Mapper completed
- Task 087 Provider Structured Output Integration Gate completed
- Task 088 Adapter-Local Structured Output Fallback Usage Spike completed
- Task 089 LM Studio Adapter-Local Structured Output Hook completed
- Task 090 Structured Output Fallback Hardening Pack completed
- Task 091 LM Studio Adapter-Local Pressure Matrix completed
- Task 092 LiteLLM Adapter-Local Hook And Pressure Tests completed
- Task 093 ProviderRuntime Structured Output Exposure Decision completed

current_governance_gate:

Task 093 ProviderRuntime Structured Output Exposure Decision

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
- typed fallback result shape implementation only after separate approval inside
  the provider_structured_output boundary
- provider_structured_output fallback result model maintenance inside its
  existing boundary only
- frontend boundary documentation and related status references only
- provider_structured_output fallback validation mapper maintenance inside its
  existing boundary only
- provider_structured_output integration-gate documentation only
- provider_structured_output adapter-local usage spike maintenance inside its
  existing boundary only
- ProviderRuntime experimental structured-output call-path implementation only
  after separate explicit Task 094 approval and with no normal turn behavior
  change

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
- promoting the fallback result shape to Core, ProviderRuntime,
  AssistantTurnRuntime, telemetry storage, or user-facing response contracts
  without separate approval
- promoting the fallback validation mapper to Core, ProviderRuntime,
  AssistantTurnRuntime, telemetry storage, provider adapters, CLI, services, or
  runtime turn flow without separate approval
- ProviderRuntime structured-output behavior changes without a separate
  approved task spec
- Core or CLI assistant-runtime provider integration without a separate approved
  task spec
- service contract implementation without separate approval
- validation script changes outside an approved validation task
- UI implementation
- real web UI implementation without a separate approved task spec
- native orb or presence shell implementation without a separate approved task
  spec
- trace/event viewer, settings surface, or voice/face visualization
  implementation without a separate approved task spec
- UI/API/WebSocket server or runtime integration without approved contracts
- UI ownership of backend/provider/runtime logic, provider selection, session
  truth, `previous_response_id` behavior, retry policy, structured-output
  parsing, tool execution, memory writes, desktop control, or policy decisions
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

Process Readiness has started. Health/version contracts, local ProcessRuntime
health/version objects, the ProcessRuntime boundary gate, future HTTP endpoint
contracts, and local CLI health/version commands have landed. No HTTP endpoint,
service daemon, subprocess runtime, provider health check, Core integration, or
ProviderRuntime integration exists.

Governance through Tasks 022, 031, 032, 042, 043B, 044B, and 045B establishes
main-first Git flow, context-budget discipline, Assistant Turn Spine,
assistant-turn contract map, runtime ownership, and library-research gates.
These gates are documentation/validation controls and do not authorize product
or runtime behavior.

Assistant-envelope work through Tasks 046B, 047, 050, 052, 054, 056, and 057
approves and implements only `InputEvent`, `AssistantTurnInput`,
`AssistantTurnResult`, and `AssistantFinalResponse`. Provider-foundation
contracts remain separate from assistant-turn contracts. Runtime integration,
tools, memory, voice, UI, desktop, proactive behavior, HTTP/IPC/service daemon
behavior, and provider bridge behavior remain blocked without separate approval.

Provider structured-output work through Tasks 070, 071, 073, 074, and 075
establishes a no-network validation boundary and fake adapter-shaped pressure
tests. The handoff remains a README/test fixture with `trace_id` and
`structured_payload`; it is not a formal Marvex contract. No provider adapter,
ProviderRuntime, Core, CLI, AssistantTurnRuntime, service, dependency, or
runtime turn behavior emits or consumes real provider-native structured output.

Tasks 078, 079, 080, and 081 record the LM Studio Responses compatibility path:
the manual harness observed that `responses.parse` with local model
`qwen3.5-0.8b` did not reliably return parsed structured objects, raw fallback
appeared only in the invalid-schema pressure case, and refusal/incomplete
semantics remain unresolved. Provider-native structured-output runtime
integration remains blocked pending better provider evidence or an accepted
fallback path.

Tasks 082, 083, and 084 define and implement the boundary-local
`StructuredOutputFallbackResult` model inside `provider_structured_output` only.
It preserves `schema_version`, `trace_id`, and `turn_id`; rejects unknown fields;
keeps `raw_preview` null by default and bounded when present; requires
JSON-compatible payload/metadata; and uses stable sanitized error codes. It is
not a Core contract, ProviderRuntime API, AssistantTurnRuntime handoff,
telemetry storage format, or user-facing response contract.

Task 085 documents the frontend/UI ownership boundary in
`docs/FRONTEND_BOUNDARY.md`: Web UI is client/presentation only, Native
Orb/Presence is future shell/presence only, and Backend/Core remains the source
of truth. Mock fixtures are allowed before backend API contracts exist, but real
integration requires approved HTTP/WebSocket contracts and a separate task spec.
Task 085 does not implement UI, native orb, presence, API/WebSocket servers,
ProviderRuntime, Core, AssistantTurnRuntime, services, or product behavior.

Latest recorded validation after Task 085 passed with `python
scripts/check_project_status.py` reporting PASS and `python
scripts/run_all_checks.py` reporting all validation checks passed.

next_allowed_work_after_task_085:

Real UI implementation remains blocked. Future frontend work requires a
separate approved static prototype, mock-only surface, or HTTP/WebSocket
contract task and must keep backend/provider/runtime logic out of UI clients.
Task 086 implements `validate_raw_structured_output(...)` inside
`provider_structured_output` only. The mapper accepts raw provider output text
plus a target Pydantic model, validates whole-output JSON only, rejects empty
output, malformed JSON, prose-wrapped JSON, brace-scraping cases, and Pydantic
validation failures as `invalid_structured_output`, and returns
`valid_structured_result` only after JSON parsing plus target-model validation.
It does not repair, scrape, retry, mutate prompts, detect refusal/incomplete
semantics, promote a handoff contract, or integrate with Core, ProviderRuntime,
AssistantTurnRuntime, CLI, services, telemetry storage, provider adapters, or
runtime turn flow.

Latest recorded validation after Task 086 passed with `python -m pytest
tests/provider_structured_output -q`, `python
scripts/check_provider_structured_output_boundaries.py`, `python
scripts/check_project_status.py`, and `python scripts/run_all_checks.py`.

next_allowed_work_after_task_086:

Runtime integration remains blocked. A future task may either keep this mapper
adapter-local for further pressure tests or separately approve integration
boundaries, but it must not move backend/provider/runtime ownership into Core,
ProviderRuntime API, AssistantTurnRuntime API, CLI, services, telemetry storage,
provider adapters, or user-facing response contracts without explicit approval.

Task 087 documents the future integration gate for provider structured-output
fallback behavior. Before any future adapter or ProviderRuntime task, the task
spec must name the exact adapter target, call path, fallback validation entry
point, deterministic invalid-output behavior, trace/turn preservation tests, and
boundary-check expectations. Provider errors/timeouts stay provider/runtime
owned, refusal/incomplete handling stays conservative without explicit provider
signals, raw provider output must not enter telemetry/logs by default, and no
Core, AssistantTurnRuntime, CLI normal-turn, service/API/WebSocket, or formal
handoff-contract promotion is authorized.

next_allowed_work_after_task_087:

Runtime integration remains blocked. The next implementation option is
adapter-local use only, behind a separate narrow approved task.

Task 088 adds `map_adapter_raw_output_to_structured_result(...)` inside
`provider_structured_output` only. It is an adapter-local usage spike that
delegates to `validate_raw_structured_output(...)`, preserves caller
`schema_version`, `trace_id`, and `turn_id`, accepts only whole-output JSON
through the existing mapper, and does not repair, scrape, retry, mutate prompts,
detect refusal/incomplete output, map provider errors/timeouts, call providers,
create a runtime API, or promote a handoff contract. It is not wired to a real
provider adapter, ProviderRuntime, Core, AssistantTurnRuntime, CLI, services,
API/WebSocket, telemetry storage, or runtime turn flow.

next_allowed_work_after_task_088:

Runtime integration remains blocked pending a separate task that names the
exact adapter target and call path.

Tasks 089 through 092 added and pressure-tested adapter-local structured-output
hooks for LM Studio Responses and LiteLLM, hardened fallback metadata and parsed
payload leakage, and preserved normal provider `send()` / `ProviderResponse`
behavior. These tasks do not expose structured output through ProviderRuntime,
Core, AssistantTurnRuntime, CLI, services, ports, contracts, telemetry storage,
or product runtime behavior.

Task 093 approves a future ProviderRuntime experimental structured-output
adapter call path only. The approved future shape is: ProviderRuntime selects an
eligible adapter, calls the adapter-local
`map_raw_output_to_structured_result(...)` method only when the adapter exposes
it, and receives `StructuredOutputFallbackResult` only inside that explicit
experimental path. LM Studio Responses and LiteLLM are initially eligible.
FakeProvider and providers without explicit adapter-local hooks remain blocked.
ProviderRuntime must not parse, repair, scrape, retry, mutate prompts, construct
fallback results, convert fallback results to `ProviderResponse` or
`AssistantTurnResult`, emit user-facing responses, or log raw provider output.

next_allowed_work_after_task_093:

Task 094 ProviderRuntime Experimental Structured Output Adapter Call Path may be
implemented only as a separate explicit task. Runtime exposure remains blocked
until then. Task 094 must not change Core, CLI normal turns,
AssistantTurnRuntime, ports, contracts, normal ProviderRuntime `send()`,
`ProviderResponse` shape, services, API/WebSocket behavior, telemetry storage,
or product runtime behavior.
