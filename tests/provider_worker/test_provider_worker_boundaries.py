from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_provider_worker_boundary_gate_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/check_provider_worker_boundaries.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS provider worker boundaries" in completed.stdout


def test_run_all_checks_includes_provider_worker_boundary_gate():
    source = (ROOT / "scripts" / "run_all_checks.py").read_text(encoding="utf-8")

    assert "check_provider_worker_boundaries.py" in source
