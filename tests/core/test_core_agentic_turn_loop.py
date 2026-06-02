from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from packages.contracts import AssistantTurnResult


ROOT = Path(__file__).resolve().parents[2]


def run_core_turn(
    text: str,
    *,
    trace_id: str,
    turn_id: str,
    extra: list[str] | None = None,
) -> AssistantTurnResult:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.core.main",
            "--turn-once",
            text,
            "--provider",
            "provider_worker",
            "--worker-provider",
            "fake",
            "--model",
            "fake-model",
            "--trace-id",
            trace_id,
            "--turn-id",
            turn_id,
            *(extra or []),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    return AssistantTurnResult.model_validate(json.loads(completed.stdout))


def test_core_worker_turn_uses_bounded_agentic_loop_and_spine_projection() -> None:
    result = run_core_turn(
        "Hello through the normal provider path",
        trace_id="trace-core-agentic-simple",
        turn_id="turn-core-agentic-simple",
    )

    loop = result.metadata["agentic_loop"]

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.metadata["assistant_turn_spine"] == "used"
    assert result.metadata["assistant_turn_spine_projection"]["trace_id"] == "trace-core-agentic-simple"
    assert result.metadata["assistant_turn_spine_projection"]["final_response_ready"] is True
    assert result.metadata["cognition"]["intent_kind"] == "provider_simple_chat"
    assert loop["max_steps"] <= 6
    assert loop["step_count"] >= 2
    assert loop["stop_reason"] == "finalized"
    assert loop["trace_id"] == "trace-core-agentic-simple"


def test_core_grounded_fresh_turn_searches_without_asking_and_returns_valid_citation() -> None:
    result = run_core_turn(
        "Give a grounded answer with current web evidence about browser-use",
        trace_id="trace-core-grounded",
        turn_id="turn-core-grounded",
        extra=["--web-search", "fake"],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "[web.evidence.1]" in result.assistant_final_response.text
    assert result.metadata["grounding"]["citation_validation"] == "citation.validated"
    assert result.metadata["grounding"]["web_search_executed"] is True
    assert result.metadata["agentic_loop"]["stop_reason"] == "finalized"


def test_core_grounded_no_evidence_never_fabricates() -> None:
    result = run_core_turn(
        "Give a grounded answer about the latest private unreleased fact",
        trace_id="trace-core-no-evidence",
        turn_id="turn-core-no-evidence",
        extra=["--web-search", "none"],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "Evidence is missing" in result.assistant_final_response.text
    assert "web.evidence." not in result.assistant_final_response.text
    assert result.metadata["grounding"]["citation_validation"] == "citation.evidence_missing"
    assert result.metadata["grounding"]["fabricated"] is False


def test_core_grounded_turn_can_use_memory_evidence_refs() -> None:
    result = run_core_turn(
        "Give a grounded answer with memory evidence about my preference",
        trace_id="trace-core-memory-grounded",
        turn_id="turn-core-memory-grounded",
        extra=["--web-search", "none", "--demo-memory-evidence"],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "[memory.evidence.chunk-demo-1]" in result.assistant_final_response.text
    assert result.metadata["grounding"]["citation_validation"] == "citation.validated"
    assert result.metadata["cognition"]["evidence_ref_count"] == 1


def test_core_safe_tool_turn_returns_real_calculator_result() -> None:
    result = run_core_turn(
        "Use the calculator tool for 2+2",
        trace_id="trace-core-real-tool",
        turn_id="turn-core-real-tool",
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "The calculator result is 4."
    assert result.metadata["tool"]["result"]["safe_result"]["result"] == "4"
    assert result.metadata["agentic_loop"]["executed_count"] == 1


def test_core_file_read_turn_executes_intent_plan_step_through_tool_worker(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "notes.txt").write_text("Marvex file executor evidence", encoding="utf-8")

    result = run_core_turn(
        "read file notes.txt",
        trace_id="trace-core-file-read",
        turn_id="turn-core-file-read",
        extra=["--file-capability-root", str(root)],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "Marvex file executor evidence" in result.assistant_final_response.text
    assert result.metadata["cognition"]["intent_kind"] == "file_read_list_search"
    assert result.metadata["intent_plan"]["step_kinds"] == ["file_read_list_search"]
    assert result.metadata["tool"]["result"]["capability_ref"]["identifier"] == "file.read"
    assert result.metadata["tool"]["result"]["trace_id"] == "trace-core-file-read"
    assert result.metadata["agentic_loop"]["executed_count"] == 1


def test_core_file_list_turn_for_desktop_pdfs_uses_tool_worker(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    desktop = root / "Desktop"
    desktop.mkdir(parents=True)
    (desktop / "invoice.pdf").write_text("pdf placeholder", encoding="utf-8")
    (desktop / "notes.txt").write_text("notes", encoding="utf-8")

    result = run_core_turn(
        "show me the PDF names on my desktop",
        trace_id="trace-core-file-list-desktop",
        turn_id="turn-core-file-list-desktop",
        extra=["--file-capability-root", str(root)],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "invoice.pdf" in result.assistant_final_response.text
    assert "notes.txt" not in result.assistant_final_response.text
    assert result.metadata["tool"]["result"]["capability_ref"]["identifier"] == "file.list"
    assert result.metadata["agentic_loop"]["executed_count"] == 1


def test_core_file_report_lookup_on_desktop_uses_rg_tool_without_approval(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    desktop = root / "Desktop"
    desktop.mkdir(parents=True)
    (desktop / "UNI Report Final.pdf").write_text("pdf placeholder", encoding="utf-8")

    result = run_core_turn(
        "I need the UNI report on Desktop",
        trace_id="trace-core-file-rg-desktop",
        turn_id="turn-core-file-rg-desktop",
        extra=["--file-capability-root", str(root)],
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "Desktop/UNI Report Final.pdf" in result.assistant_final_response.text
    assert result.metadata["tool"]["result"]["capability_ref"]["identifier"] == "file.rg"
    assert result.metadata["agentic_loop"]["executed_count"] == 1


def test_core_list_tools_uses_capability_diagnostics_not_provider() -> None:
    result = run_core_turn(
        "list tools",
        trace_id="trace-core-list-tools",
        turn_id="turn-core-list-tools",
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "Capabilities available" in result.assistant_final_response.text
    assert result.provider_turn_refs == []
    assert result.metadata["tool"]["result"]["capability_ref"]["identifier"] == "builtin.capability_diagnostics"
    assert result.metadata["agentic_loop"]["executed_count"] == 1


def test_core_file_write_turn_pauses_for_approval_instead_of_provider() -> None:
    result = run_core_turn(
        "write test.txt on my desktop",
        trace_id="trace-core-write-approval",
        turn_id="turn-core-write-approval",
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "Approval required" in result.assistant_final_response.text
    assert result.provider_turn_refs == []
    assert result.metadata["agentic_loop"]["stop_reason"] == "waiting_for_human_approval"
    assert result.metadata["approval_request"]["approval_request_id"] == "approval-turn-core-write-approval"


def test_core_routes_non_provider_intent_kinds_without_generic_provider_fallthrough() -> None:
    cases = [
        (
            "list MCP tools",
            "mcp_needed",
            "tool",
            lambda result: (
                result.metadata["tool"]["result"]["capability_ref"]["identifier"] == "mcp.local.echo"
                and result.metadata["tool"]["projection"]["executed_fake_capability_count"] == 0
            ),
        ),
        (
            "use the MCP skill echo",
            "mcp_skill",
            "tool",
            lambda result: (
                result.metadata["tool"]["result"]["capability_ref"]["identifier"] == "mcp.local.echo"
                and result.metadata["tool"]["projection"]["executed_fake_capability_count"] == 0
            ),
        ),
        (
            "what do you remember about my preferences",
            "memory",
            "memory",
            lambda result: result.metadata["memory"]["raw_memory_content_persisted"] is False,
        ),
        (
            "use skill safe-writing",
            "skill_needed",
            "skill",
            lambda result: result.metadata["skill"]["install_launch_enabled"] is False,
        ),
        (
            "connect my Gmail account",
            "connector_account",
            "connector",
            lambda result: result.metadata["connector"]["live_oauth_started"] is False,
        ),
        (
            "show control plane settings",
            "settings_control_plane",
            "settings",
            lambda result: result.metadata["settings"]["approval_resume_supported"] is True,
        ),
        (
            "open browser page",
            "browser_computer_use",
            "browser",
            lambda result: result.metadata["browser"]["live_browser_executed"] is False,
        ),
    ]

    for index, (prompt, intent_kind, metadata_key, extra_assertion) in enumerate(cases):
        result = run_core_turn(
            prompt,
            trace_id=f"trace-core-route-{index}",
            turn_id=f"turn-core-route-{index}",
        )

        assert result.assistant_final_response is not None, prompt
        assert result.metadata["intent"]["selected_intent"]["intent_kind"] == intent_kind, prompt
        assert result.metadata["intent_plan"]["step_kinds"] == [intent_kind], prompt
        assert metadata_key in result.metadata, prompt
        if intent_kind == "memory":
            assert result.provider_turn_refs != [], prompt
            assert result.metadata["provider_boundary"] == "provider_worker_process", prompt
        else:
            assert result.provider_turn_refs == [], prompt
            assert "provider_boundary" not in result.metadata, prompt
        assert result.metadata["agentic_loop"]["trace_id"] == f"trace-core-route-{index}", prompt
        assert extra_assertion(result), prompt


def test_core_approval_required_can_resume_approve_deny_and_cancel() -> None:
    paused = run_core_turn(
        "delete this file",
        trace_id="trace-core-approval",
        turn_id="turn-core-approval",
    )

    approval = paused.metadata["approval_request"]
    approval_id = approval["approval_request_id"]

    assert paused.error is None
    assert paused.assistant_final_response is not None
    assert paused.assistant_final_response.finish_reason.value == "stop"
    assert "approval required" in paused.assistant_final_response.text.lower()
    assert paused.metadata["agentic_loop"]["stop_reason"] == "waiting_for_human_approval"

    approved = run_core_turn(
        "delete this file",
        trace_id="trace-core-approval",
        turn_id="turn-core-approval",
        extra=["--resume-approval", approval_id, "--approval-decision", "approve"],
    )
    denied = run_core_turn(
        "delete this file",
        trace_id="trace-core-deny",
        turn_id="turn-core-deny",
        extra=["--resume-approval", "approval-turn-core-deny", "--approval-decision", "deny"],
    )
    cancelled = run_core_turn(
        "delete this file",
        trace_id="trace-core-cancel",
        turn_id="turn-core-cancel",
        extra=["--resume-approval", "approval-turn-core-cancel", "--approval-decision", "cancel"],
    )

    assert approved.error is not None
    assert approved.error.details["reason"] == "approval_resume_missing_model_tool_call"
    assert approved.metadata["approval"]["decision"] == "approved"
    assert approved.metadata["tool_boundary"] == "model_tool_call_required"
    assert approved.metadata["agentic_loop"]["executed_count"] == 0

    assert denied.error is not None
    assert denied.error.details["reason"] == "approval_denied"
    assert denied.metadata["approval"]["decision"] == "denied"

    assert cancelled.error is not None
    assert cancelled.error.details["reason"] == "approval_cancelled"
    assert cancelled.metadata["approval"]["decision"] == "cancelled"


def test_core_approval_resume_requires_same_logical_turn_approval_id() -> None:
    result = run_core_turn(
        "delete this file",
        trace_id="trace-core-invalid-approval",
        turn_id="turn-core-invalid-approval",
        extra=["--resume-approval", "approval-from-another-turn", "--approval-decision", "approve"],
    )

    assert result.error is not None
    assert result.error.details["reason"] == "approval_resume_mismatch"
    assert result.metadata["approval"]["decision"] == "mismatched"
    assert result.metadata["agentic_loop"]["stop_reason"] == "blocked"
    assert result.metadata["agentic_loop"]["executed_count"] == 0


def test_core_approval_resume_does_not_execute_parsed_file_write_without_model_tool_call(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    (root / "Desktop").mkdir(parents=True)
    turn_id = "turn-core-write-resume"
    paused = run_core_turn(
        "write test.txt on my desktop",
        trace_id="trace-core-write-resume",
        turn_id=turn_id,
        extra=["--file-capability-root", str(root)],
    )

    approved = run_core_turn(
        "write test.txt on my desktop",
        trace_id="trace-core-write-resume",
        turn_id=turn_id,
        extra=[
            "--file-capability-root",
            str(root),
            "--resume-approval",
            paused.metadata["approval_request"]["approval_request_id"],
            "--approval-decision",
            "approve",
        ],
    )

    assert approved.error is not None
    assert approved.error.details["reason"] == "approval_resume_missing_model_tool_call"
    assert approved.metadata["tool_boundary"] == "model_tool_call_required"
    assert not (root / "Desktop" / "test.txt").exists()


def test_core_approval_resume_does_not_execute_browser_text_without_model_tool_call() -> None:
    turn_id = "turn-core-browser-resume"
    paused = run_core_turn(
        "use playwright to open example.com",
        trace_id="trace-core-browser-resume",
        turn_id=turn_id,
    )

    approved = run_core_turn(
        "use playwright to open example.com",
        trace_id="trace-core-browser-resume",
        turn_id=turn_id,
        extra=[
            "--resume-approval",
            paused.metadata["approval_request"]["approval_request_id"],
            "--approval-decision",
            "approve",
        ],
    )

    assert approved.error is not None
    assert approved.error.details["reason"] == "approval_resume_missing_model_tool_call"
    assert approved.metadata["tool_boundary"] == "model_tool_call_required"
    assert "automation" not in approved.metadata
