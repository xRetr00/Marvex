from __future__ import annotations

import json
import subprocess
import sys


def test_core_loopback_provider_smoke_captures_system_user_memory_and_evidence_request() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/smoke_core_prompt_fidelity.py",
            "--text",
            "Using the evidence, what project codename do I prefer?",
            "--seed-memory",
            "User preferred project codename is Cedar.",
            "--seed-evidence",
            "Evidence says Cedar is the preferred codename.",
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)

    assert payload["status"] == "PASS"
    assert payload["provider_name"] == "lmstudio_responses"
    assert payload["request_has_instructions"] is True
    assert payload["request_has_real_question"] is True
    assert payload["request_has_real_memory"] is True
    assert payload["request_has_real_evidence"] is True
    assert payload["request_uses_adaptive_budget"] is True
    assert payload["raw_payload_persisted"] is False

