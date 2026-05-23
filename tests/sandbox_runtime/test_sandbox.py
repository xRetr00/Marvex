from __future__ import annotations

from pathlib import Path

from packages.sandbox_runtime import (
    SandboxPolicy,
    ShellExecutor,
    WriteFileExecutor,
    sandbox_tool_spec,
)
from packages.capability_runtime import (
    ApprovalDecision,
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


def _request(identifier: str, arguments: dict[str, object], *, side_effect: ToolSideEffectLevel) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=identifier)
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="p1",
        trace_id="t1",
        turn_id="tn1",
        capability_ref=ref,
        proposed_action=identifier,
        risk_level=ToolRiskLevel.HIGH,
        side_effect_level=side_effect,
        execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
        arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="perm1",
        capability_ref=ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    approval = ApprovalDecision(
        schema_version="1",
        decision_id="appr1",
        approval_request_id="ar1",
        capability_ref=ref,
        decision="approved",
        decided_by="user",
    )
    return CapabilityExecutionRequest(
        schema_version="1",
        request_id="r1",
        trace_id="t1",
        turn_id="tn1",
        proposal=proposal,
        permission_decision=permission,
        approval_decision=approval,
        arguments=arguments,
        execution_mode=CapabilityExecutionMode.APPROVED_EXECUTE,
    )


def _policy(tmp_path: Path) -> SandboxPolicy:
    return SandboxPolicy(write_roots=(str(tmp_path.resolve()),))


def test_policy_allows_within_root_denies_outside_and_traversal(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert policy.is_path_allowed(tmp_path / "notes" / "a.txt") is True
    assert policy.is_path_allowed(tmp_path.parent / "outside.txt") is False
    assert policy.is_path_allowed(tmp_path / ".." / "escape.txt") is False


def test_policy_denies_secret_paths(tmp_path: Path) -> None:
    policy = SandboxPolicy(write_roots=(str(tmp_path.resolve()),))
    assert policy.is_path_allowed(tmp_path / ".ssh" / "id_rsa") is False
    assert policy.is_path_allowed(tmp_path / ".env") is False


def test_write_creates_file_without_persisting_raw_content(tmp_path: Path) -> None:
    executor = WriteFileExecutor(policy=_policy(tmp_path))
    target = tmp_path / "sub" / "hello.txt"
    result = executor.execute(_request("file.write", {"path": str(target), "content": "hello world"}, side_effect=ToolSideEffectLevel.WRITE_LOCAL))
    assert result.status == "succeeded"
    assert result.safe_result["created"] is True
    assert result.safe_result["raw_content_persisted"] is False
    assert "content" not in result.safe_result
    assert target.read_text(encoding="utf-8") == "hello world"


def test_write_outside_root_is_denied(tmp_path: Path) -> None:
    executor = WriteFileExecutor(policy=_policy(tmp_path))
    outside = tmp_path.parent / "evil.txt"
    result = executor.execute(_request("file.write", {"path": str(outside), "content": "x"}, side_effect=ToolSideEffectLevel.WRITE_LOCAL))
    assert result.status == "denied"
    assert result.safe_result["reason_code"] == "sandbox.write_denied"
    assert not outside.exists()


def test_mkdir_and_delete_within_root(tmp_path: Path) -> None:
    executor = WriteFileExecutor(policy=_policy(tmp_path))
    d = tmp_path / "newdir"
    made = executor.execute(_request("file.mkdir", {"path": str(d)}, side_effect=ToolSideEffectLevel.WRITE_LOCAL))
    assert made.status == "succeeded" and d.is_dir()
    f = tmp_path / "rm.txt"
    f.write_text("bye", encoding="utf-8")
    deleted = executor.execute(_request("file.delete", {"path": str(f)}, side_effect=ToolSideEffectLevel.DESTRUCTIVE))
    assert deleted.status == "succeeded" and not f.exists()


def test_shell_runs_safe_command_and_caps_output(tmp_path: Path) -> None:
    executor = ShellExecutor(policy=_policy(tmp_path))
    result = executor.execute(_request("shell.run", {"command": "echo marvex_ok"}, side_effect=ToolSideEffectLevel.DESTRUCTIVE))
    assert result.status == "succeeded"
    assert result.safe_result["exit_code"] == 0
    assert "marvex_ok" in str(result.safe_result["stdout_preview"])
    assert result.safe_result["raw_command_persisted"] is False


def test_shell_denies_destructive_command(tmp_path: Path) -> None:
    executor = ShellExecutor(policy=_policy(tmp_path))
    result = executor.execute(_request("shell.run", {"command": "rm -rf /"}, side_effect=ToolSideEffectLevel.DESTRUCTIVE))
    assert result.status == "denied"
    assert result.safe_result["reason_code"] == "sandbox.command_denied"


def test_unsupported_capability_is_denied(tmp_path: Path) -> None:
    executor = WriteFileExecutor(policy=_policy(tmp_path))
    result = executor.execute(_request("file.read", {"path": str(tmp_path / "a")}, side_effect=ToolSideEffectLevel.WRITE_LOCAL))
    assert result.status == "denied"
    assert result.safe_result["reason_code"] == "sandbox.unsupported_capability"


def test_sandbox_tool_spec_classification() -> None:
    write = sandbox_tool_spec("file.write")
    assert write.risk_level == ToolRiskLevel.HIGH
    assert write.side_effect_level == ToolSideEffectLevel.WRITE_LOCAL
    assert write.requires_approval is True
    shell = sandbox_tool_spec("shell.run")
    assert shell.side_effect_level == ToolSideEffectLevel.DESTRUCTIVE
