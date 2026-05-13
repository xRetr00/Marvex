import subprocess
import sys
from pathlib import Path


def test_local_api_boundary_gate_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/check_local_api_boundaries.py"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
