# Project Status

current_phase: agent_context_budget_validation_gate

implementation_status: process_readiness_cli_health_version_completed

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

current_governance_gate:

Task 050 Assistant Envelope Contract Semantic Revision

allowed_current_work:

- documentation
- templates
- project status updates
- Git workflow governance
- approved task slices only

forbidden_current_work:

- unapproved product behavior changes
- runtime behavior changes
- endpoint behavior changes
- provider behavior changes
- CLI behavior changes
- telemetry runtime behavior changes
- contract model behavior changes
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

next_allowed_work_after_task_032:

Only a small approved task slice after an approved task plan. Likely candidates
are future service-runtime planning, governance cleanup, or another narrow
Process Readiness slice; no further implementation is authorized by this status
file.
