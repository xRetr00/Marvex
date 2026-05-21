from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from packages.contracts import AssistantTurnResult


ROOT = Path(__file__).resolve().parents[2]


def test_core_entrypoint_exposes_provider_selection_flags():
    completed = subprocess.run(
        [sys.executable, "-m", "services.core.main", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--provider" in completed.stdout
    assert "provider_worker" in completed.stdout
    assert "--model" in completed.stdout
    assert "--base-url" in completed.stdout
    assert "--timeout" in completed.stdout


def test_core_provider_worker_roundtrip_command_uses_real_worker_process():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.core.main",
            "--turn-once",
            "Hello through ProviderWorker",
            "--provider",
            "provider_worker",
            "--model",
            "fake-model",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    result = AssistantTurnResult.model_validate(payload)
    assert result.trace_id == "trace-core-provider-worker-turn-once"
    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "fake provider response"
    assert result.provider_turn_refs[0].provider_name == "fake"
    assert payload["metadata"]["provider_boundary"] == "provider_worker_process"


def test_core_provider_worker_roundtrip_propagates_trace_id():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.core.main",
            "--turn-once",
            "Trace me",
            "--provider",
            "provider_worker",
            "--trace-id",
            "trace-custom-core-worker",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = AssistantTurnResult.model_validate(json.loads(completed.stdout))

    assert result.trace_id == "trace-custom-core-worker"
    assert result.provider_turn_refs[0].trace_id == "trace-custom-core-worker"


def test_core_provider_worker_unsupported_provider_returns_error_envelope():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.core.main",
            "--turn-once",
            "Unsupported",
            "--provider",
            "provider_worker",
            "--worker-provider",
            "unknown",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = AssistantTurnResult.model_validate(json.loads(completed.stdout))

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code.value == "PROVIDER_UNAVAILABLE"
    assert result.error.source == "assistant_runtime"
