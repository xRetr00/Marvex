# Project Status

current_phase: status_readme_drift_cleanup

implementation_status: process_readiness_local_runtime_completed

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

completed_governance_gates:

- Task 018 Provider Foundation Governance Cleanup
- Task 021 ProcessRuntime Boundary Validation Gate
- Task 022 Git Workflow Governance completed
- Task 023 Process Readiness Architecture Audit completed

current_governance_gate:

Task 024 Status and README Drift Cleanup

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

next_allowed_work_after_task_024:

Only a small approved task slice. Likely options are CLI health/version command
or HTTP endpoint contract planning after an approved task plan.
