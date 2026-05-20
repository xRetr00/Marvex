from __future__ import annotations

from scripts.check_governance_classification import REQUIRED_SURFACES, validate_governance_classifications


def test_governance_gate_requires_all_major_surfaces_to_be_classified() -> None:
    docs = {
        "docs/GOVERNANCE_CLASSIFICATION.md": "provider foundation | approved implementation surface\n",
        "docs/CONTRACT_APPROVALS.md": "Existing code is not approval.\n",
        "PROJECT_STATUS.md": "governance_reconciliation_boundary_hardening_complete\n",
    }

    failures = validate_governance_classifications(docs)

    assert any("assistant turn integration" in failure for failure in failures)
    assert len(failures) >= len(REQUIRED_SURFACES) - 1


def test_governance_gate_accepts_explicit_classifications_and_code_not_approval_rule() -> None:
    classification_rows = "\n".join(
        f"| {surface} | bounded foundation | owner | notes |"
        for surface in REQUIRED_SURFACES
    )
    docs = {
        "docs/GOVERNANCE_CLASSIFICATION.md": "Existing code is not approval.\ndocumented surface\nbounded foundation\nevaluation seam\ndraft service contract\npolicy-controlled surface\nsafety-restricted surface\nfuture product surface\ndocs/CONTRACT_APPROVALS.md\n" + classification_rows,
        "docs/CONTRACT_APPROVALS.md": "Existing code is not approval.\ncontract approval and contract status live only in docs/CONTRACT_APPROVALS.md\n",
        "PROJECT_STATUS.md": "governance_reconciliation_boundary_hardening_complete\nnext recommended goal: foundation cleanup\n",
        "services/voice_worker/README.md": "Contract status: see `docs/CONTRACT_APPROVALS.md`\n",
    }

    assert validate_governance_classifications(docs) == []

