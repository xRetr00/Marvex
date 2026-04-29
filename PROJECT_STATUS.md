# Project Status

current_phase: agent_context_architecture_governance

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

current_governance_gate:

Task 031 Agent Context Architecture governance

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

next_allowed_work_after_task_031:

Only a small approved task slice after an approved task plan. Likely candidates
are a Task 032 validation gate for Context Pack requirements or a future
service-runtime planning slice; no further
implementation is authorized by this status file.
