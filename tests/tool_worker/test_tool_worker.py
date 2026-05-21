from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_worker_jsonl(commands: list[dict[str, object]]) -> list[dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, "-m", "services.tool_worker.main", "--jsonl"],
        cwd=ROOT,
        input="".join(json.dumps(command) + "\n" for command in commands),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    return [json.loads(line) for line in completed.stdout.splitlines()]


def test_tool_worker_is_no_longer_readme_only() -> None:
    entries = {path.name for path in (ROOT / "services" / "tool_worker").iterdir()}

    assert {"README.md", "__init__.py", "models.py", "controller.py", "main.py"}.issubset(entries)


def test_tool_worker_entrypoint_help_health_and_version_are_runnable() -> None:
    help_result = subprocess.run(
        [sys.executable, "-m", "services.tool_worker.main", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    health_result = subprocess.run(
        [sys.executable, "-m", "services.tool_worker.main", "--health-once"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    version_result = subprocess.run(
        [sys.executable, "-m", "services.tool_worker.main", "--version-once"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "--jsonl" in help_result.stdout
    assert "--health-once" in help_result.stdout
    assert health_result.returncode == 0, health_result.stdout + health_result.stderr
    assert version_result.returncode == 0, version_result.stdout + version_result.stderr
    assert json.loads(health_result.stdout)["service"] == "marvex-tool-worker"
    assert json.loads(version_result.stdout)["service"] == "marvex-tool-worker"


def test_tool_worker_jsonl_start_status_execute_safe_capability_and_stop() -> None:
    responses = run_worker_jsonl(
        [
            {"command": "start", "trace_id": "trace-tool-worker"},
            {"command": "status", "trace_id": "trace-tool-worker"},
            {
                "command": "execute",
                "trace_id": "trace-tool-worker",
                "turn_id": "turn-tool-worker",
                "capability_id": "fake.status",
                "action": "read",
                "capability": "read",
                "resource_type": "local_status",
                "arguments": {"raw_secret": "must-not-leak"},
            },
            {"command": "stop", "trace_id": "trace-tool-worker"},
        ]
    )

    assert [response["command"] for response in responses] == [
        "start",
        "status",
        "execute",
        "stop",
    ]
    assert all(response["ok"] is True for response in responses)
    result = responses[2]["result"]
    projection = responses[2]["projection"]
    audit = responses[2]["policy_audit"]
    serialized = json.dumps(responses)

    assert result["status"] == "succeeded"
    assert result["trace_id"] == "trace-tool-worker"
    assert result["raw_input_persisted"] is False
    assert result["raw_output_persisted"] is False
    assert projection["safe_result_status"] == "succeeded"
    assert audit["decision"] == "allow"
    assert audit["raw_payload_persisted"] is False
    assert "must-not-leak" not in serialized
    assert "raw_secret" not in serialized


def test_tool_worker_blocks_unapproved_write_execution() -> None:
    responses = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-tool-blocked",
                "turn_id": "turn-tool-blocked",
                "capability_id": "fake.status",
                "action": "write generated file",
                "capability": "file_write",
                "resource_type": "file",
                "arguments": {"path": "secret.txt", "contents": "must-not-leak"},
            }
        ]
    )

    response = responses[0]
    serialized = json.dumps(response)

    assert response["ok"] is False
    assert response["blocked"] is True
    assert response["result"]["status"] == "requires_human_approval"
    assert response["policy_audit"]["decision"] == "approval_required"
    assert response["error"]["code"] == "approval_required"
    assert "must-not-leak" not in serialized
    assert "secret.txt" not in serialized


def test_tool_worker_returns_structured_error_for_invalid_command() -> None:
    responses = run_worker_jsonl([{"command": "execute", "trace_id": "trace-invalid"}])

    assert responses[0]["ok"] is False
    assert responses[0]["error"]["code"] == "validation_error"
    assert responses[0]["error"]["trace_id"] == "trace-invalid"
