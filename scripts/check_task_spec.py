from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKS = [
    "1. Create architecture docs.",
    "2. Create contracts docs.",
    "3. Create AI agent rules.",
    "4. Create process, IPC, telemetry, library, and validation docs.",
    "5. Create project skeleton.",
    "6. Add contracts only.",
    "7. Add fake provider.",
    "8. Add Python Core Service.",
    "9. Add telemetry trace lifecycle.",
    "10. Add LM Studio Responses Provider and CLI vertical slice.",
]
REQUIRED_TEMPLATE_FIELDS = [
    "goal:",
    "allowed_files:",
    "forbidden_files:",
    "contract_impact:",
    "ownership_boundary:",
    "single_ownership_boundary:",
    "standalone_module_owner:",
    "why_not_central_orchestration:",
    "god_object_avoidance:",
    "dependency_direction:",
    "port_minimal_method_surface:",
    "port_forbidden_implementation_names:",
    "port_runtime_owner_for_selection_dispatch:",
    "port_god_file_prevention:",
    "file_size_risk:",
    "tests_required:",
    "validation_commands:",
    "rollback_plan:",
    "final_report_required:",
]


def main() -> int:
    failures = []
    if not (ROOT / "templates/TASK_SPEC.md").is_file():
        failures.append("missing templates/TASK_SPEC.md")
    else:
        template = (ROOT / "templates/TASK_SPEC.md").read_text(encoding="utf-8")
        for field in REQUIRED_TEMPLATE_FIELDS:
            if field not in template:
                failures.append(f"task spec template missing field: {field}")

    task_plan = (ROOT / "docs/TASK_PLAN.md").read_text(encoding="utf-8")
    task_plan_lower = task_plan.lower()
    for task in TASKS:
        if task not in task_plan:
            failures.append(f"missing required task entry: {task}")

    if "a real task spec file" not in task_plan_lower:
        failures.append("task plan must require a real task spec file")
    if "task id alone is not sufficient" not in task_plan_lower and "not only a task id" not in task_plan_lower:
        failures.append("task plan must reject task-id-only implementation gating")

    required_sections = [
        "Goal:",
        "Allowed files:",
        "Forbidden files:",
        "Required tests/checks:",
        "Acceptance criteria:",
        "Failure conditions:",
        "Required final report format:",
    ]
    for section in required_sections:
        if task_plan.count(section) < 10:
            failures.append(f"each task must include section: {section}")

    for rel in ["docs/VALIDATION_GATES.md", "docs/AI_AGENT_RULES.md"]:
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        if "task id alone" not in text and "task id as a substitute" not in text:
            failures.append(f"{rel} must reject task-id-only work")
        if "real task spec file" not in text:
            failures.append(f"{rel} must require a real task spec file")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS task spec and task plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
