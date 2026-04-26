from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"


def main() -> int:
    failures: list[str] = []
    text = PROJECT_STATUS.read_text(encoding="utf-8")
    lowered = text.lower()

    if "implementation_status: skeleton_only" in lowered:
        failures.append("PROJECT_STATUS.md still says implementation_status: skeleton_only")
    if "task 006 contracts-only" in lowered:
        failures.append("PROJECT_STATUS.md still points next_allowed_task at Task 006")
    if "provider foundation completed" not in lowered:
        failures.append("PROJECT_STATUS.md must state Provider Foundation completed")
    if "task 018 provider foundation governance cleanup" not in lowered:
        failures.append("PROJECT_STATUS.md must identify Task 018 as the current cleanup gate")
    if "process readiness" not in lowered:
        failures.append("PROJECT_STATUS.md must identify Process Readiness as the next subsystem")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS project status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
