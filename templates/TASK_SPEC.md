# Task Spec Template

task_id:

title:

goal:

allowed_files:

forbidden_files:

context_pack:

  required_files_to_inspect:

  optional_files_to_inspect:

  forbidden_read_areas:

  search_scope:

  large_file_read_policy:

  full_repo_scan_allowed:

  context_budget_risk:

  scope_expansion_approval_required:

contract_impact:

contract_approval_required:

assistant_turn_spine_gate:

  Assistant Turn Spine gate required for assistant-level work.

  Provider Turn is not Assistant Turn.

  This section must explain how the task avoids turning provider turn into assistant turn.

  where_does_this_fit_in_assistant_turn_spine:

  which contract owns its input:

  which_contract_owns_input:

  which contract owns its output:

  which_contract_owns_output:

  is_contract_approved_for_implementation:

  which runtime owns dispatch:

  which_runtime_owns_dispatch_selection_lifecycle_or_composition:

  which_port_is_minimal_boundary:

  which_adapter_owns_external_library_or_protocol_code:

  which maintained library was considered:

  which_maintained_library_sdk_or_repo_was_considered_before_custom_code:

  if_custom_code_why_no_maintained_option_is_suitable:

  how_this_avoids_turning_provider_turn_into_assistant_turn:

  how_this_avoids_growing_TurnOrchestrator_into_god_object:

  how_this_avoids_expanding_ProviderRuntime_into_routing_fallback_session_history:

  how_this_preserves_future_process_separation:

  how_trace_id_is_propagated:

  where_policy_checks_are_enforced:

  what_is_explicitly_forbidden:

assistant_turn_contract_map_gate:

  input_output_contracts_named:

  contract_approval_status_identified:

  provider_foundation_contracts_not_repurposed:

  assistant_level_contract_family_required:

  current_contract_is_provider_foundation_only:

runtime_ownership_gate:

  which_runtime_owns_this_work:

  is_runtime_approved_for_implementation:

  which_contract_owns_runtime_input:

  which_contract_owns_runtime_output:

  which_layer_owns_dispatch:

  which_layer_owns_selection:

  which_layer_owns_lifecycle:

  which_layer_owns_failure_cancellation_behavior:

  how_trace_id_is_propagated:

  which_policy_checkpoints_apply:

  which_maintained_library_sdk_or_repo_was_considered_before_custom_code:

  avoid_expanding_core_into_god_object:

  avoid_expanding_assistantturnruntime_into_subsystem_internals:

  avoid_expanding_providerruntime_into_routing_session_history_fallback:

  avoid_putting_memory_tool_policy_behavior_into_contextbuilder:

  explicitly_forbidden_for_this_task:

ownership_boundary:

single_ownership_boundary:

standalone_module_owner:

why_not_central_orchestration:

god_object_avoidance:

dependency_direction:

port_minimal_method_surface:

port_forbidden_implementation_names:

port_runtime_owner_for_selection_dispatch:

port_god_file_prevention:

file_size_risk:

library_decisions_required:

tests_required:

validation_commands:

git_workflow_required:

branch_required:

commit_required:

push_required:

rollback_plan:

acceptance_criteria:

failure_conditions:

final_report_required:
