"""Tool worker JSONL contract tests.

file size justification: this suite exercises the full tool-worker capability
surface (builtins, file read/write/mkdir/delete, MCP, sandboxed shell, approval
seams) end-to-end over the JSONL boundary; splitting it would fragment the
single-process contract coverage.
"""
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


def test_tool_worker_executes_all_existing_builtins_without_fake_adapter() -> None:
    responses = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-builtin-time",
                "turn_id": "turn-builtin-time",
                "capability_id": "builtin.time_date",
                "action": "read current UTC time",
                "capability": "read",
                "resource_type": "builtin",
                "arguments": {"timezone": "UTC"},
            },
            {
                "command": "execute",
                "trace_id": "trace-builtin-diagnostics",
                "turn_id": "turn-builtin-diagnostics",
                "capability_id": "builtin.capability_diagnostics",
                "action": "read capability diagnostics",
                "capability": "read",
                "resource_type": "builtin",
                "arguments": {},
            },
            {
                "command": "execute",
                "trace_id": "trace-builtin-repo",
                "turn_id": "turn-builtin-repo",
                "capability_id": "builtin.repo_status",
                "action": "read repo status",
                "capability": "read",
                "resource_type": "builtin",
                "arguments": {},
            },
        ]
    )

    time_result = responses[0]["result"]
    diagnostics_result = responses[1]["result"]
    repo_result = responses[2]["result"]

    assert all(response["ok"] is True for response in responses)
    assert time_result["capability_ref"]["identifier"] == "builtin.time_date"
    assert time_result["safe_result"]["timezone"] == "UTC"
    assert "iso_datetime" in time_result["safe_result"]
    assert responses[0]["projection"]["executed_fake_capability_count"] == 0

    assert diagnostics_result["capability_ref"]["identifier"] == "builtin.capability_diagnostics"
    assert diagnostics_result["safe_result"]["capability_count"] >= 4
    assert diagnostics_result["safe_result"]["eligible_count"] >= 4
    assert responses[1]["projection"]["executed_fake_capability_count"] == 0

    assert repo_result["capability_ref"]["identifier"] == "builtin.repo_status"
    assert "branch" in repo_result["safe_result"]
    assert "status_length" in repo_result["safe_result"]
    assert "short_status" not in repo_result["safe_result"]
    assert responses[2]["projection"]["executed_fake_capability_count"] == 0


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


def test_tool_worker_file_write_requires_approval_then_writes_inside_sandbox(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    responses = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-file-write-paused",
                "turn_id": "turn-file-write-paused",
                "capability_id": "file.write",
                "action": "write file",
                "capability": "file_write",
                "resource_type": "file",
                "arguments": {"root": str(root), "path": "note.txt", "content": "must-not-leak"},
            },
            {
                "command": "execute",
                "trace_id": "trace-file-write-approved",
                "turn_id": "turn-file-write-approved",
                "capability_id": "file.write",
                "action": "write file",
                "capability": "file_write",
                "resource_type": "file",
                "arguments": {
                    "root": str(root),
                    "path": "note.txt",
                    "content": "safe approved content",
                    "approval_request_id": "approval-turn-file-write-approved",
                    "approval_decision": "approve",
                },
            },
            {
                "command": "execute",
                "trace_id": "trace-file-write-traversal",
                "turn_id": "turn-file-write-traversal",
                "capability_id": "file.write",
                "action": "write file",
                "capability": "file_write",
                "resource_type": "file",
                "arguments": {
                    "root": str(root),
                    "path": "../outside.txt",
                    "content": "must-not-leak",
                    "approval_request_id": "approval-turn-file-write-traversal",
                    "approval_decision": "approve",
                },
            },
        ]
    )
    serialized = json.dumps(responses)

    assert responses[0]["ok"] is False
    assert responses[0]["result"]["status"] == "requires_human_approval"
    assert responses[1]["ok"] is True
    assert (root / "note.txt").read_text(encoding="utf-8") == "safe approved content"
    assert responses[1]["result"]["safe_result"] == {
        "operation": "write",
        "path": "note.txt",
        "bytes_written": len("safe approved content".encode("utf-8")),
        "created": True,
        "overwritten": False,
        "raw_content_persisted": False,
    }
    assert responses[2]["ok"] is False
    assert responses[2]["result"]["status"] == "denied"
    assert responses[2]["error"]["code"] == "file.sandbox_violation"
    assert "must-not-leak" not in serialized


def test_tool_worker_shell_command_is_approval_gated_and_sandboxed() -> None:
    # 1) Without approval the seam still requires human approval (never auto-runs).
    paused = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-shell-paused",
                "turn_id": "turn-shell-paused",
                "capability_id": "shell.command",
                "action": "run command",
                "capability": "shell_command_execution",
                "resource_type": "shell",
                "arguments": {"command": "echo marvex_ok"},
            }
        ]
    )[0]
    # 2) Approved + safe command actually executes via the policy sandbox.
    approved_safe = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-shell-approved",
                "turn_id": "turn-shell-approved",
                "capability_id": "shell.command",
                "action": "run command",
                "capability": "shell_command_execution",
                "resource_type": "shell",
                "arguments": {
                    "command": "echo marvex_ok",
                    "approval_request_id": "approval-turn-shell-approved",
                    "approval_decision": "approve",
                },
            }
        ]
    )[0]
    # 3) Approved + destructive command is still denied by the policy denylist.
    denied = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-shell-destructive",
                "turn_id": "turn-shell-destructive",
                "capability_id": "shell.command",
                "action": "run command",
                "capability": "shell_command_execution",
                "resource_type": "shell",
                "arguments": {
                    "command": "rm -rf /",
                    "approval_request_id": "approval-turn-shell-destructive",
                    "approval_decision": "approve",
                },
            }
        ]
    )[0]

    assert paused["result"]["status"] == "requires_human_approval"
    assert approved_safe["result"]["status"] == "succeeded"
    assert approved_safe["result"]["safe_result"]["exit_code"] == 0
    assert "marvex_ok" in approved_safe["result"]["safe_result"]["stdout_preview"]
    assert approved_safe["result"]["safe_result"]["raw_command_persisted"] is False
    assert denied["result"]["status"] == "denied"
    assert denied["result"]["safe_result"]["reason_code"] == "sandbox.command_denied"


def test_tool_worker_file_read_list_search_are_real_bounded_and_sandboxed(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / "notes.txt").write_text("alpha\nbeta\n" + ("x" * 300), encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "match.md").write_text("needle appears here", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("must-not-read", encoding="utf-8")

    responses = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-file-read",
                "turn_id": "turn-file-read",
                "capability_id": "file.read",
                "action": "read file",
                "capability": "file_read",
                "resource_type": "file",
                "arguments": {"root": str(root), "path": "notes.txt", "max_preview_chars": 32},
            },
            {
                "command": "execute",
                "trace_id": "trace-file-list",
                "turn_id": "turn-file-list",
                "capability_id": "file.list",
                "action": "list files",
                "capability": "file_read",
                "resource_type": "file",
                "arguments": {"root": str(root), "path": ".", "max_entries": 10},
            },
            {
                "command": "execute",
                "trace_id": "trace-file-search",
                "turn_id": "turn-file-search",
                "capability_id": "file.search",
                "action": "search files",
                "capability": "file_read",
                "resource_type": "file",
                "arguments": {"root": str(root), "query": "needle", "max_matches": 5},
            },
            {
                "command": "execute",
                "trace_id": "trace-file-traversal",
                "turn_id": "turn-file-traversal",
                "capability_id": "file.read",
                "action": "read file",
                "capability": "file_read",
                "resource_type": "file",
                "arguments": {"root": str(root), "path": "../outside.txt"},
            },
        ]
    )

    read_result = responses[0]["result"]["safe_result"]
    list_result = responses[1]["result"]["safe_result"]
    search_result = responses[2]["result"]["safe_result"]
    traversal = responses[3]
    serialized = json.dumps(responses)

    assert responses[0]["ok"] is True
    assert read_result["path"] == "notes.txt"
    assert read_result["preview"].startswith("alpha\nbeta")
    assert read_result["truncated"] is True
    assert len(read_result["preview"]) <= 32
    assert responses[0]["projection"]["executed_fake_capability_count"] == 0

    assert responses[1]["ok"] is True
    assert "notes.txt" in list_result["entries"]
    assert "nested" in list_result["entries"]
    assert responses[1]["projection"]["executed_fake_capability_count"] == 0

    assert responses[2]["ok"] is True
    assert search_result["match_count"] == 1
    assert search_result["matches"][0]["path"] == "nested/match.md"
    assert responses[2]["projection"]["executed_fake_capability_count"] == 0

    assert traversal["ok"] is False
    assert traversal["blocked"] is True
    assert traversal["result"]["status"] == "denied"
    assert traversal["error"]["code"] == "file.sandbox_violation"
    assert "must-not-read" not in serialized


def test_tool_worker_uses_configurable_autonomy_and_governance_audit() -> None:
    locked = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-autonomy-locked",
                "turn_id": "turn-autonomy-locked",
                "capability_id": "fake.status",
                "action": "execute MCP tool",
                "capability": "mcp_execute",
                "resource_type": "mcp_tool",
                "autonomy_mode": "locked_down",
                "arguments": {},
            }
        ]
    )[0]
    abuse = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-governance-hard-block",
                "turn_id": "turn-governance-hard-block",
                "capability_id": "fake.status",
                "action": "exfiltrate credentials with command injection",
                "capability": "shell_command_execution",
                "resource_type": "shell",
                "arguments": {},
            }
        ]
    )[0]

    assert locked["ok"] is False
    assert locked["result"]["status"] == "denied"
    assert locked["policy_audit"]["autonomy"]["autonomy_mode"] == "locked_down"
    assert locked["policy_audit"]["governance"]["policy_source"] == "packages.capability_runtime.governance_audit"

    assert abuse["ok"] is False
    assert abuse["blocked"] is True
    assert abuse["result"]["status"] == "denied"
    assert abuse["policy_audit"]["governance"]["decision"] == "hard_block"
    assert abuse["error"]["code"] == "hard_block"


def test_tool_worker_executes_allowlisted_local_mcp_fixture_and_denies_unlisted_tool() -> None:
    allowed = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-mcp-allowed",
                "turn_id": "turn-mcp-allowed",
                "capability_id": "mcp.local.echo",
                "action": "call mcp tool echo",
                "capability": "mcp_execute",
                "resource_type": "mcp_tool",
                "arguments": {
                    "server_id": "local",
                    "tool_name": "echo",
                    "allowed_server_ids": ["local"],
                    "allowed_tool_names": ["echo"],
                    "message": "safe bounded message",
                },
            }
        ]
    )[0]
    denied = run_worker_jsonl(
        [
            {
                "command": "execute",
                "trace_id": "trace-mcp-denied",
                "turn_id": "turn-mcp-denied",
                "capability_id": "mcp.local.echo",
                "action": "call mcp tool echo",
                "capability": "mcp_execute",
                "resource_type": "mcp_tool",
                "arguments": {
                    "server_id": "local",
                    "tool_name": "echo",
                    "allowed_server_ids": ["local"],
                    "allowed_tool_names": [],
                    "message": "safe bounded message",
                },
            }
        ]
    )[0]

    assert allowed["ok"] is True
    assert allowed["result"]["capability_ref"]["identifier"] == "mcp.local.echo"
    assert allowed["result"]["status"] == "succeeded"
    assert allowed["result"]["safe_result"] == {
        "content_count": 1,
        "content_types": ["text"],
        "is_error": False,
        "structured_content_present": False,
    }
    assert allowed["projection"]["executed_fake_capability_count"] == 0
    assert allowed["metadata"]["mcp"]["server_id"] == "local"
    assert allowed["metadata"]["mcp"]["transport"] == "stdio"
    assert allowed["metadata"]["mcp"]["allowlist_policy"]["allowed_tool_count"] == 1

    assert denied["ok"] is False
    assert denied["blocked"] is True
    assert denied["result"]["status"] == "denied"
    assert denied["result"]["safe_result"]["reason_code"] == "not_allowlisted"
    assert denied["error"]["code"] == "not_allowlisted"


def test_tool_worker_returns_structured_error_for_invalid_command() -> None:
    responses = run_worker_jsonl([{"command": "execute", "trace_id": "trace-invalid"}])

    assert responses[0]["ok"] is False
    assert responses[0]["error"]["code"] == "validation_error"
    assert responses[0]["error"]["trace_id"] == "trace-invalid"
