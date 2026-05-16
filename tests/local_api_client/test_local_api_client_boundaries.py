import subprocess
import sys
from pathlib import Path


def test_local_api_client_boundary_gate_passes_for_current_source():
    root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [sys.executable, "scripts/check_local_api_client_boundaries.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS local API client boundaries" in completed.stdout
