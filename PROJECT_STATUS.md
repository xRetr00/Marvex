# Project Status

current_phase: provider_foundation_governance_cleanup

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

current_cleanup_gate:

Task 018 Provider Foundation Governance Cleanup

allowed_current_work:

- documentation
- templates
- validation scripts
- README governance updates
- library decision records
- schema-version reference cleanup in docs and tests
- approved task slices only

forbidden_current_work:

- unapproved product behavior changes
- provider behavior changes
- CLI behavior changes
- telemetry runtime behavior changes
- contract model behavior changes
- UI implementation
- tools
- memory
- voice
- desktop context
- proactive behavior
- vision

status_rule:

Provider Foundation completed. Task 018 is a cleanup gate to align documentation,
dependency governance, schema-version policy, and validation with the completed
foundation before starting the next subsystem.

next_subsystem_after_cleanup:

Process Readiness.
