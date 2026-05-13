from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"
README = ROOT / "README.md"
PROCESS_RUNTIME = ROOT / "packages" / "process_runtime" / "process_runtime.py"


def _section_value(text: str, section_name: str) -> str:
    lines = text.splitlines()
    section_header = f"{section_name}:"
    for index, line in enumerate(lines):
        if line.strip().lower() != section_header:
            continue

        values: list[str] = []
        for next_line in lines[index + 1 :]:
            stripped = next_line.strip()
            if stripped.endswith(":") and not stripped.startswith("-"):
                break
            if stripped:
                values.append(stripped)
        return "\n".join(values).lower()

    return ""


def _require_phrase(
    *,
    text: str,
    phrase: str,
    failures: list[str],
    message: str,
) -> None:
    if phrase.lower() not in text:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    status_text = PROJECT_STATUS.read_text(encoding="utf-8")
    status_lowered = status_text.lower()
    readme_lowered = README.read_text(encoding="utf-8").lower()
    current_gate = _section_value(status_text, "current_governance_gate")

    if "implementation_status: skeleton_only" in status_lowered:
        failures.append("PROJECT_STATUS.md still says implementation_status: skeleton_only")
    if "task 006 contracts-only" in status_lowered:
        failures.append("PROJECT_STATUS.md still points next_allowed_task at Task 006")
    if (
        PROCESS_RUNTIME.is_file()
        and "implementation_status: provider_foundation_completed" in status_lowered
    ):
        failures.append(
            "PROJECT_STATUS.md has stale implementation_status after ProcessRuntime was added"
        )
    if "task 018" in current_gate or "task 022" in current_gate:
        failures.append("PROJECT_STATUS.md current_governance_gate points to stale Task 018/022")

    _require_phrase(
        text=status_lowered,
        phrase="provider foundation completed",
        failures=failures,
        message="PROJECT_STATUS.md must state Provider Foundation completed",
    )
    _require_phrase(
        text=status_lowered,
        phrase="process readiness has started",
        failures=failures,
        message="PROJECT_STATUS.md must state Process Readiness has started",
    )
    _require_phrase(
        text=status_lowered,
        phrase="processruntime boundary gate completed",
        failures=failures,
        message="PROJECT_STATUS.md must state ProcessRuntime boundary gate completed",
    )
    _require_phrase(
        text=status_lowered,
        phrase="task 024 status and readme drift cleanup",
        failures=failures,
        message="PROJECT_STATUS.md must identify Task 024 as the current cleanup gate",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="process readiness has started",
        failures=failures,
        message="README.md must state Process Readiness has started",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="processruntime",
        failures=failures,
        message="README.md must mention ProcessRuntime",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="local `processruntime` health/version provider",
        failures=failures,
        message="README.md must mention the local ProcessRuntime health/version provider",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="local health/version api app object",
        failures=failures,
        message="README.md must mention the local health/version API app object",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="no turn endpoint exists yet",
        failures=failures,
        message="README.md must state no turn endpoint exists yet",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="no service daemon exists yet",
        failures=failures,
        message="README.md must state no service daemon exists yet",
    )
    _require_phrase(
        text=readme_lowered,
        phrase="no subprocess runtime",
        failures=failures,
        message="README.md must state no subprocess runtime exists yet",
    )

    if "process readiness has started" not in readme_lowered:
        failures.append("README.md and PROJECT_STATUS.md must agree Process Readiness has started")
    if "process readiness has started" not in status_lowered:
        failures.append("PROJECT_STATUS.md and README.md must agree Process Readiness has started")

    if "provider foundation completed" not in status_lowered:
        failures.append("PROJECT_STATUS.md must state Provider Foundation completed")
    if "process readiness" not in status_lowered:
        failures.append("PROJECT_STATUS.md must identify Process Readiness")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS project status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
