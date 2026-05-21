from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_intent_worker_boundary_gate_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_intent_worker_boundaries.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS intent worker boundaries" in completed.stdout


def test_run_all_checks_includes_intent_worker_boundary_gate() -> None:
    source = (ROOT / "scripts" / "run_all_checks.py").read_text(encoding="utf-8")

    assert "check_intent_worker_boundaries.py" in source
