# Project Status

current_phase: git_workflow_governance

implementation_status: provider_foundation_completed

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

- Task 019 Health and Version Contract Slice
- Task 020 Health/Version Runtime Provider
- Task 021 ProcessRuntime Boundary Validation Gate

completed_governance_gates:

- Task 018 Provider Foundation Governance Cleanup
- Task 021 ProcessRuntime Boundary Validation Gate

current_governance_gate:

Task 022 Marvex Git Workflow Rules

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

Process Readiness has completed the contract slice, local health/version runtime
provider, and ProcessRuntime boundary validation gate through Task 021.

Task 022 is the current Git workflow governance gate. It establishes the default
main-first task flow, branch approval requirement, and commit/push discipline for
future Marvex tasks.

next_subsystem_after_cleanup:

Process Readiness.
