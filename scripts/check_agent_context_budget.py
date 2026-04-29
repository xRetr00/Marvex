from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_MAP = ROOT / "docs" / "SYSTEM_MAP.md"
MODULE_INDEX = ROOT / "docs" / "MODULE_INDEX.md"
AGENT_CONTEXT_RULES = ROOT / "docs" / "AGENT_CONTEXT_RULES.md"
AI_AGENT_RULES = ROOT / "docs" / "AI_AGENT_RULES.md"
TASK_PLAN = ROOT / "docs" / "TASK_PLAN.md"
TASK_SPEC_TEMPLATE = ROOT / "templates" / "TASK_SPEC.md"

REQUIRED_DOCS = [
    SYSTEM_MAP,
    MODULE_INDEX,
    AGENT_CONTEXT_RULES,
]

REQUIRED_CONTEXT_PACK_FIELDS = [
    "context_pack:",
    "required_files_to_inspect",
    "optional_files_to_inspect",
    "forbidden_read_areas",
    "search_scope",
    "large_file_read_policy",
    "full_repo_scan_allowed",
    "context_budget_risk",
    "scope_expansion_approval_required",
]

REQUIRED_CONTEXT_RULE_PHRASES = [
    "do not scan the full repository by default",
    "do not run broad `rg` without a target folder",
    "do not run repo-wide `rg --files` unless",
    "large file reads require",
    "ask for approval before widening read scope",
]


def _read_lower(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8").lower()


def main() -> int:
    failures: list[str] = []

    for path in REQUIRED_DOCS:
        if not path.is_file():
            failures.append(f"missing {path.relative_to(ROOT).as_posix()}")

    ai_agent_rules = _read_lower(AI_AGENT_RULES, failures)
    task_plan = _read_lower(TASK_PLAN, failures)
    task_spec_template = _read_lower(TASK_SPEC_TEMPLATE, failures)
    agent_context_rules = (
        AGENT_CONTEXT_RULES.read_text(encoding="utf-8").lower()
        if AGENT_CONTEXT_RULES.is_file()
        else ""
    )

    if AI_AGENT_RULES.is_file() and "docs/agent_context_rules.md" not in ai_agent_rules:
        failures.append("docs/AI_AGENT_RULES.md must mention docs/AGENT_CONTEXT_RULES.md")

    if TASK_PLAN.is_file() and "context pack" not in task_plan:
        failures.append("docs/TASK_PLAN.md must mention Context Pack")

    if TASK_SPEC_TEMPLATE.is_file():
        for field in REQUIRED_CONTEXT_PACK_FIELDS:
            if field not in task_spec_template:
                failures.append(f"templates/TASK_SPEC.md missing context pack field: {field}")

    if AGENT_CONTEXT_RULES.is_file():
        for phrase in REQUIRED_CONTEXT_RULE_PHRASES:
            if phrase not in agent_context_rules:
                failures.append(
                    f"docs/AGENT_CONTEXT_RULES.md missing core rule phrase: {phrase}"
                )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS agent context budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
