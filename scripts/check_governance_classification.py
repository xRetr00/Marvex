from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = (
    "docs/GOVERNANCE_CLASSIFICATION.md",
    "docs/CONTRACT_APPROVALS.md",
    "PROJECT_STATUS.md",
    "services/voice_worker/README.md",
)
REQUIRED_CLASSIFICATIONS = (
    "documented surface",
    "bounded foundation",
    "evaluation seam",
    "draft service contract",
    "policy-controlled surface",
    "safety-restricted surface",
    "future product surface",
)
REQUIRED_SURFACES = (
    "provider foundation",
    "assistant turn contracts",
    "assistant turn integration",
    "telemetry",
    "local api",
    "control plane api",
    "control plane web",
    "capability runtime",
    "tool execution foundations",
    "mcp adapter/seam",
    "browser/computer-use adapter/seam",
    "memory runtime",
    "marketplace runtime",
    "session runtime",
    "intent/prompt harness seams",
    "service placeholders",
    "future voice",
    "voice worker runtime",
    "future desktop agent",
    "shell product surface",
    "future orb ui",
    "future proactive behavior",
    "future vision",
)
STATUS_PHRASES = (
    "existing code is not approval",
    "docs/contract_approvals.md",
    "contract approval and contract status live only in docs/contract_approvals.md",
)
STATUS_REQUIRED_PHRASES = (
    "governance_reconciliation_boundary_hardening_complete",
    "next recommended goal",
)


def _normalize(text: str) -> str:
    return text.lower().replace("`", "")


def read_governance_docs() -> dict[str, str]:
    return {
        rel: (ROOT / rel).read_text(encoding="utf-8") if (ROOT / rel).is_file() else ""
        for rel in REQUIRED_DOCS
    }


def validate_governance_classifications(docs: dict[str, str]) -> list[str]:
    failures: list[str] = []
    combined = _normalize("\n".join(docs.values()))
    classification = _normalize(docs.get("docs/GOVERNANCE_CLASSIFICATION.md", ""))
    approvals = _normalize(docs.get("docs/CONTRACT_APPROVALS.md", ""))
    status = _normalize(docs.get("PROJECT_STATUS.md", ""))
    voice_worker_service = _normalize(docs.get("services/voice_worker/README.md", ""))

    for rel in REQUIRED_DOCS:
        if not docs.get(rel):
            failures.append(f"missing governance classification input: {rel}")

    for label in REQUIRED_CLASSIFICATIONS:
        if label not in classification:
            failures.append(f"governance classification doc missing label: {label}")

    for surface in REQUIRED_SURFACES:
        if surface not in classification:
            failures.append(f"governance classification doc missing surface: {surface}")

    for phrase in STATUS_PHRASES:
        if phrase not in combined:
            failures.append(f"governance docs missing status phrase: {phrase}")
        if phrase not in approvals:
            failures.append(f"CONTRACT_APPROVALS.md missing status phrase: {phrase}")

    for phrase in STATUS_REQUIRED_PHRASES:
        if phrase not in status:
            failures.append(f"PROJECT_STATUS.md missing current cleanup phrase: {phrase}")

    if "contract status: see docs/contract_approvals.md" not in voice_worker_service:
        failures.append("VoiceWorker service README must point contract status at docs/CONTRACT_APPROVALS.md")

    stale_next = (
        "recommended next: add a local service composition slice",
        "recommended next: add a persisted approval/trace resumption service slice",
        "recommended next: add a narrow assistantRuntime consumption proof".lower(),
    )
    for phrase in stale_next:
        if phrase in status:
            failures.append(f"PROJECT_STATUS.md still contains stale recommended next phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate_governance_classifications(read_governance_docs())
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS governance classification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
