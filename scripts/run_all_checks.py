from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent

CHECKS = [
    "check_workspace_policy.py",
    "check_docs_accepted.py",
    "check_service_placeholders.py",
    "check_forbidden_modules.py",
    "check_task_spec.py",
    "check_agent_context_budget.py",
    "check_assistant_turn_spine.py",
    "check_assistant_turn_contract_map.py",
    "check_assistant_turn_envelope.py",
    "check_assistant_turn_contract_drafts.py",
    "check_assistant_runtime_boundaries.py",
    "check_session_runtime_boundaries.py",
    "check_memory_runtime_boundaries.py",
    "check_capability_runtime_boundaries.py",
    "check_mcp_adapter_boundaries.py",
    "check_skills_runtime_boundaries.py",
    "check_full_tooling_boundaries.py",
    "check_agent_execution_loop_boundaries.py",
    "check_control_plane_boundaries.py",
    "check_intent_context_prompt_boundaries.py",
    "check_end_to_end_turn_boundaries.py",
    "check_assistant_intelligence_tool_runtime_boundaries.py",
    "check_provider_structured_output_boundaries.py",
    "check_telemetry_boundaries.py",
    "check_runtime_ownership.py",
    "check_library_research_matrix.py",
    "check_library_decisions.py",
    "check_schema_versions.py",
    "check_project_status.py",
    "check_file_size_policy.py",
    "check_port_boundaries.py",
    "check_decision_runtime_boundaries.py",
    "check_provider_runtime_boundaries.py",
    "check_runtime_composition_boundaries.py",
    "check_local_api_boundaries.py",
    "check_local_api_client_boundaries.py",
    "check_local_service_startup_boundaries.py",
    "check_process_runtime_boundaries.py",
    "check_vaxil_boundary.py",
]


def main() -> int:
    results = []
    for check in CHECKS:
        path = SCRIPT_DIR / check
        print(f"RUN {check}")
        completed = subprocess.run([sys.executable, str(path)], cwd=ROOT)
        results.append((check, completed.returncode))

    print("\nSummary")
    failed = False
    for check, code in results:
        status = "PASS" if code == 0 else "FAIL"
        print(f"{status} {check}")
        failed = failed or code != 0

    if failed:
        print("FAIL validation failed")
        return 1

    print("PASS all validation checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
