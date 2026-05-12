import subprocess
import sys
from pathlib import Path


def test_runtime_composition_boundary_gate_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/check_runtime_composition_boundaries.py"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS runtime composition boundaries" in completed.stdout
