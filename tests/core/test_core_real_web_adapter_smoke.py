from __future__ import annotations

import json
import subprocess
import sys


def test_core_searxng_adapter_smoke_exercises_grounded_web_path():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/smoke_core_real_web_adapter.py",
            "--text",
            "Give a grounded answer with current web evidence about browser-use",
        ],
        text=True,
        capture_output=True,
        timeout=40,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)

    assert payload["status"] == "PASS"
    assert payload["web_provider"] == "searxng"
    assert payload["citation_validation"] == "citation.validated"
    assert payload["request_count"] == 1
    assert payload["response_contains_citation"] is True
    assert payload["trace_id"] == "trace-smoke-real-web-adapter"
