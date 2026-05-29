"""Tests for the per-file filesystem tools (docs/TODO/07, increment 2)."""

from pathlib import Path

import pytest

from packages.adapters.capabilities.files import (
    FileCapabilityError,
    ReadOnlyFileExecutor,
    SandboxedFileWriteExecutor,
)
from packages.adapters.capabilities.tools import (
    ToolRegistry,
    WriteFileTool,
    file_tools_registry,
)
from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


def _request(identifier: str, arguments: dict[str, object]) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=identifier)
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="p-1",
        trace_id="t-1",
        turn_id="u-1",
        capability_ref=ref,
        proposed_action="file",
        risk_level=ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
        arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="d-1",
        capability_ref=ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    return CapabilityExecutionRequest(
        schema_version="1",
        request_id="r-1",
        trace_id="t-1",
        turn_id="u-1",
        proposal=proposal,
        permission_decision=permission,
        arguments=arguments,
    )


def test_write_creates_new_file(tmp_path: Path):
    result = WriteFileTool().execute(
        _request("file.write", {"root": str(tmp_path), "path": "a.txt", "content": "hello"})
    )
    assert result.status == "succeeded"
    assert result.safe_result["write_mode"] == "create"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello"


def test_write_existing_appends_by_default(tmp_path: Path):
    (tmp_path / "a.txt").write_text("first", encoding="utf-8")
    result = WriteFileTool().execute(
        _request("file.write", {"root": str(tmp_path), "path": "a.txt", "content": "second"})
    )
    assert result.status == "succeeded"
    assert result.safe_result["write_mode"] == "append"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "first\nsecond"


def test_write_existing_overwrite_replaces(tmp_path: Path):
    (tmp_path / "a.txt").write_text("first", encoding="utf-8")
    result = WriteFileTool().execute(
        _request("file.write", {"root": str(tmp_path), "path": "a.txt", "content": "new", "overwrite": True})
    )
    assert result.safe_result["write_mode"] == "overwrite"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "new"


def test_write_executor_no_longer_hard_fails_on_existing(tmp_path: Path):
    """B1 regression guard: writing to an existing file must not raise file.exists."""
    (tmp_path / "a.txt").write_text("first", encoding="utf-8")
    result = SandboxedFileWriteExecutor().execute(
        _request("file.write", {"root": str(tmp_path), "path": "a.txt", "content": "more"})
    )
    assert result.status == "succeeded"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "first\nmore"


def test_patch_append_and_replace(tmp_path: Path):
    (tmp_path / "log.txt").write_text("line1\n", encoding="utf-8")
    appended = file_tools_registry().execute(
        _request("file.patch", {"root": str(tmp_path), "path": "log.txt", "content": "line2", "mode": "append"})
    )
    assert appended.safe_result["patch_mode"] == "append"
    assert (tmp_path / "log.txt").read_text(encoding="utf-8") == "line1\nline2"

    replaced = file_tools_registry().execute(
        _request("file.patch", {"root": str(tmp_path), "path": "log.txt", "content": "fresh", "mode": "replace"})
    )
    assert replaced.safe_result["patch_mode"] == "replace"
    assert (tmp_path / "log.txt").read_text(encoding="utf-8") == "fresh"


def test_read_executor_cannot_write(tmp_path: Path):
    """The read-only executor must refuse a write capability id."""
    with pytest.raises(FileCapabilityError) as exc:
        ReadOnlyFileExecutor().execute(
            _request("file.write", {"root": str(tmp_path), "path": "x.txt", "content": "nope"})
        )
    assert exc.value.code == "file.unsupported_capability"
    assert not (tmp_path / "x.txt").exists()


def test_read_and_list_roundtrip(tmp_path: Path):
    (tmp_path / "note.txt").write_text("the quick brown fox", encoding="utf-8")
    read = ReadOnlyFileExecutor().execute(
        _request("file.read", {"root": str(tmp_path), "path": "note.txt"})
    )
    assert read.safe_result["operation"] == "read"
    assert "quick brown" in read.safe_result["preview"]

    listing = ReadOnlyFileExecutor().execute(
        _request("file.list", {"root": str(tmp_path), "path": "."})
    )
    assert "note.txt" in listing.safe_result["entries"]


def test_file_tools_registry_exposes_all_six_schemas():
    registry = file_tools_registry()
    ids = {s["function"]["name"] for s in registry.tool_schemas()}
    assert ids == {"file.read", "file.list", "file.search", "file.rg", "file.write", "file.patch"}


def test_write_content_too_large_rejected(tmp_path: Path):
    with pytest.raises(FileCapabilityError) as exc:
        WriteFileTool().execute(
            _request("file.write", {"root": str(tmp_path), "path": "big.txt", "content": "x" * 20_000})
        )
    assert exc.value.code == "file.content_too_large"


def test_rg_matches_named_report_from_natural_phrasing(tmp_path: Path):
    """B3 (find half): 'read the contents of the my uni report on desktop'
    must match a University_Report.pdf instead of returning nothing."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Hospital_System_Supreme_University_Report.pdf").write_bytes(b"%PDF-1.4 stub")
    (desktop / "Vaxil_System_Supreme_University_Report.pdf").write_bytes(b"%PDF-1.4 stub")
    (desktop / "unrelated_notes.txt").write_text("nothing", encoding="utf-8")

    result = file_tools_registry().execute(
        _request(
            "file.rg",
            {
                "root": str(tmp_path),
                "path": "Desktop",
                # Full-sentence query, as produced from a natural request.
                "query": "read the contents of the my uni report on desktop tell me how good is it",
            },
        )
    )
    assert result.status == "succeeded"
    names = [m["name"] for m in result.safe_result["matches"]]
    # The two University_Report PDFs should match (university contains 'uni',
    # plus 'report'); the unrelated note should not.
    assert any("University_Report" in n for n in names)
    assert "unrelated_notes.txt" not in names


def test_rg_ranks_higher_overlap_first(tmp_path: Path):
    (tmp_path / "uni_report_final.txt").write_text("x", encoding="utf-8")
    (tmp_path / "report_only.txt").write_text("x", encoding="utf-8")
    result = file_tools_registry().execute(
        _request("file.rg", {"root": str(tmp_path), "path": ".", "query": "uni report"})
    )
    names = [m["name"] for m in result.safe_result["matches"]]
    # The file matching both tokens ranks before the one matching a single token.
    assert names[0] == "uni_report_final.txt"
