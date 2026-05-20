from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_core_service_boundary_gate_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/check_core_service_boundaries.py"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS core service boundaries" in completed.stdout
