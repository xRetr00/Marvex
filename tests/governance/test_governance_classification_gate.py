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
        f"| {surface} | bounded foundation: implementation exists, but expansion is blocked without explicit approval | owner | blocked |"
        for surface in REQUIRED_SURFACES
    )
    docs = {
        "docs/GOVERNANCE_CLASSIFICATION.md": "Existing code is not approval.\napproved implementation surface\nbounded foundation\nexperimental seam\nfuture service contract\nforbidden product behavior for now\ndocs/CONTRACT_APPROVALS.md\n" + classification_rows,
        "docs/CONTRACT_APPROVALS.md": "Existing code is not approval.\ncurrent goal spec\nPROJECT_STATUS.md\nvalidation gates\nrelevant architecture docs\n",
        "PROJECT_STATUS.md": "governance_reconciliation_boundary_hardening_complete\nnext recommended goal: foundation cleanup\n",
    }

    assert validate_governance_classifications(docs) == []

