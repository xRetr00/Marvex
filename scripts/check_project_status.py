from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"
README = ROOT / "README.md"
GOVERNANCE_CLASSIFICATION = ROOT / "docs" / "GOVERNANCE_CLASSIFICATION.md"
ROADMAP = ROOT / "docs" / "ROADMAP.md"

REQUIRED_STATUS_PHRASES = (
    "current_phase: adaptive_context_evidence_memory_learning_governance_complete",
    "implementation_status: adaptive_context_evidence_memory_learning_governance_complete",
    "accepted_docs: true",
    "Existing foundations are now classified",
    "CapabilityRuntime remains authoritative",
    "Assistant turn integration coordinates approved runtime layers",
    "Next Recommended Goal",
)
FORBIDDEN_STATUS_PHRASES = (
    "recommended next: add a local service composition slice",
    "recommended next: add a persisted approval/trace resumption service slice",
    "recommended next: add a narrow assistantruntime consumption proof",
    "next_allowed_task",
    "task 006 contracts-only",
)
REQUIRED_GOVERNANCE_PHRASES = (
    "Existing code is not approval",
    "approved implementation surface",
    "bounded foundation",
    "experimental seam",
    "future service contract",
    "forbidden product behavior for now",
)
REQUIRED_ROADMAP_PHRASES = (
    "bounded internal foundations",
    "not product expansion approval",
    "governance reconciliation, boundary hardening, and foundation cleanup",
    "Existing code is not approval",
)


def _require_phrase(text: str, phrase: str, failures: list[str], message: str) -> None:
    if phrase.lower() not in text.lower():
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    status_text = PROJECT_STATUS.read_text(encoding="utf-8") if PROJECT_STATUS.is_file() else ""
    governance_text = GOVERNANCE_CLASSIFICATION.read_text(encoding="utf-8") if GOVERNANCE_CLASSIFICATION.is_file() else ""
    roadmap_text = ROADMAP.read_text(encoding="utf-8") if ROADMAP.is_file() else ""
    readme_text = README.read_text(encoding="utf-8") if README.is_file() else ""

    for phrase in REQUIRED_STATUS_PHRASES:
        _require_phrase(status_text, phrase, failures, f"PROJECT_STATUS.md missing current-state phrase: {phrase}")
    for phrase in FORBIDDEN_STATUS_PHRASES:
        if phrase in status_text.lower():
            failures.append(f"PROJECT_STATUS.md contains stale next-step phrase: {phrase}")
    for phrase in REQUIRED_GOVERNANCE_PHRASES:
        _require_phrase(governance_text, phrase, failures, f"docs/GOVERNANCE_CLASSIFICATION.md missing phrase: {phrase}")
    for phrase in REQUIRED_ROADMAP_PHRASES:
        _require_phrase(roadmap_text, phrase, failures, f"docs/ROADMAP.md missing cleanup phrase: {phrase}")

    if "process readiness has started" not in readme_text.lower():
        failures.append("README.md must retain Process Readiness baseline wording")
    if "local health/version api app object" not in readme_text.lower():
        failures.append("README.md must retain local health/version API baseline wording")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS project status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
