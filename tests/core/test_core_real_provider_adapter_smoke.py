from __future__ import annotations

import json
import subprocess
import sys


def test_core_lmstudio_responses_adapter_smoke_exercises_provider_worker_path():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/smoke_core_real_provider_adapter.py",
            "--text",
            "Reply with the word Marvex.",
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)

    assert payload["status"] == "PASS"
    assert payload["provider_name"] == "lmstudio_responses"
    assert payload["provider_boundary"] == "provider_worker_process"
    assert payload["assistant_turn_spine"] == "used"
    assert payload["response_text"] == "Marvex real provider adapter smoke."
    assert payload["trace_id"] == "trace-smoke-real-provider-adapter"
