from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "services" / "core" / "main.py"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

REQUIRED_TERMS = (
    "_AgenticLoopProjection",
    "max_steps",
    "step_count",
    "stop_reason",
    "waiting_for_human_approval",
    "validate_grounded_citations",
    "citation.evidence_missing",
    "fabricated",
    "_run_approval_path",
    "--resume-approval",
    "--approval-decision",
    "assistant_turn_spine",
    "raw_payload_persisted",
)
FORBIDDEN_TOKENS = (
    "while True",
    "for _ in itertools.count",
    "raw_prompt_persisted=True",
    "raw_context_persisted=True",
    "raw_payload_persisted=True",
    "bypass_policy",
    "policy_bypass",
)
REQUIRED_DOC_PHRASES = (
    "approval resume works",
    "grounding is enforced",
    "bounded Agentic Turn Loop",
)


def main() -> int:
    failures: list[str] = []
    text = CORE.read_text(encoding="utf-8") if CORE.is_file() else ""
    if not text:
        failures.append("services/core/main.py is missing")
    for term in REQUIRED_TERMS:
        if term not in text:
            failures.append(f"services/core/main.py missing agentic loop term: {term}")
    for token in FORBIDDEN_TOKENS:
        if token in text:
            failures.append(f"services/core/main.py contains forbidden agentic loop token: {token}")
    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_core_agentic_turn_loop_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_core_agentic_turn_loop_boundaries.py")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"agentic loop docs/status missing phrase: {phrase}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS core agentic turn loop boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
