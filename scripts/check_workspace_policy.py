from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "docs",
    "docs/diagrams",
    "templates",
    "services/core",
    "services/provider_worker",
    "services/tool_worker",
    "services/intent_worker",
    "services/voice_worker",
    "services/desktop_agent",
    "services/shell",
    "apps/cli",
    "apps/future_qt_shell",
    "packages/contracts",
    "packages/core",
    "packages/ports",
    "packages/adapters",
    "packages/telemetry",
    "tests/contract",
    "tests/core",
    "tests/adapters",
    "tests/api",
    "tests/replay",
    "tests/process",
    "scripts",
]

REQUIRED_FILES = [
    "README.md",
    "PROJECT_STATUS.md",
    "VAXIL_REFERENCE.md",
    "docs/ARCHITECTURE.md",
    "docs/PROCESS_MODEL.md",
    "docs/CONTRACTS.md",
    "docs/CONTRACT_APPROVALS.md",
    "docs/IPC_API.md",
    "docs/TELEMETRY.md",
    "docs/LIBRARY_POLICY.md",
    "docs/SUBPROCESS_RULES.md",
    "docs/CORE_RULES.md",
    "docs/AI_AGENT_RULES.md",
    "docs/VALIDATION_GATES.md",
    "docs/TASK_PLAN.md",
    "docs/ROADMAP.md",
    "docs/RISKS.md",
    "docs/ACCEPTANCE_CRITERIA.md",
    "docs/SERVICE_PLACEHOLDER_POLICY.md",
    "templates/TASK_SPEC.md",
    "templates/RFC.md",
    "templates/CONTRACT_CHANGE.md",
    "templates/SERVICE_README.md",
    "templates/VALIDATION_REPORT.md",
    "templates/AGENT_FINAL_REPORT.md",
    "templates/LIBRARY_DECISION.md",
    "templates/ERROR_ENVELOPE.md",
    "templates/TRACE_EVENT.md",
]

SOURCE_SUFFIXES = {
    ".py",
    ".pyw",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".cs",
}


def accepted_docs() -> bool:
    status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    return "accepted_docs: true" in status.lower()


def status_text() -> str:
    return (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8").lower()


def validate_contract_registry() -> list[str]:
    failures = []
    path = ROOT / "docs/CONTRACT_APPROVALS.md"
    if not path.is_file():
        return ["missing required file: docs/CONTRACT_APPROVALS.md"]

    text = path.read_text(encoding="utf-8").lower()
    required_columns = [
        "contract_name",
        "schema_version",
        "approval_status",
        "approver",
        "approval_date",
        "implementation_allowed",
    ]
    for column in required_columns:
        if column not in text:
            failures.append(f"contract approval registry missing column: {column}")

    for line in text.splitlines():
        if not line.startswith("|") or "---" in line or "contract_name" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            failures.append(f"contract approval row must have 6 columns: {line}")
            continue
        name, _, status, approver, date, allowed = cells
        if status not in {"draft", "approved", "deprecated", "blocked"}:
            failures.append(f"{name} has invalid approval_status: {status}")
        if allowed not in {"yes", "no"}:
            failures.append(f"{name} has invalid implementation_allowed: {allowed}")
        if allowed == "yes" and status != "approved":
            failures.append(f"{name} allows implementation without approved status")
        if status == "approved" and (approver == "none" or date == "none"):
            failures.append(f"{name} approved without approver/date")

    return failures


def main() -> int:
    failures = []

    for rel in REQUIRED_DIRS:
        if not (ROOT / rel).is_dir():
            failures.append(f"missing required directory: {rel}")

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            failures.append(f"missing required file: {rel}")

    docs_accepted = accepted_docs()
    project_status = status_text()
    if not docs_accepted:
        if "current_phase: planning_only" not in project_status:
            failures.append("accepted_docs false requires current_phase: planning_only")
        if "implementation_status: not_started" not in project_status:
            failures.append("accepted_docs false requires implementation_status: not_started")

    failures.extend(validate_contract_registry())

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in SOURCE_SUFFIXES and not rel.startswith("scripts/"):
            if not docs_accepted:
                failures.append(f"product implementation before docs acceptance: {rel}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS workspace policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
