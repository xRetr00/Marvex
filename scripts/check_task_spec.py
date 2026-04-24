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


def main() -> int:
    failures = []
    if not (ROOT / "templates/TASK_SPEC.md").is_file():
        failures.append("missing templates/TASK_SPEC.md")

    task_plan = (ROOT / "docs/TASK_PLAN.md").read_text(encoding="utf-8")
    for task in TASKS:
        if task not in task_plan:
            failures.append(f"missing required task entry: {task}")

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

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS task spec and task plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

