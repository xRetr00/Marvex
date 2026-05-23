"""Marvex policy sandbox for write + shell capabilities.

This is intentionally NOT a VM/container isolation layer. The agent operates on
the real local filesystem so it can genuinely help on the user's PC — but every
mutating action is:

  1. gated by CapabilityRuntime approval (CapabilityExecutionRequest cannot even
     be constructed without an approved permission + human approval for risky
     capabilities), and
  2. constrained by a SandboxPolicy (path allowlist + denied system/secret
     locations + a destructive-command denylist + timeouts + output caps).

No raw file content or raw command text is persisted in the safe result.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from pydantic import Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.capability_runtime.models import CapabilityRuntimeModel

WRITE_CAPABILITIES = ("file.write", "file.mkdir", "file.delete")
SHELL_CAPABILITIES = ("shell.run", "shell.command")
SANDBOX_CAPABILITIES = WRITE_CAPABILITIES + SHELL_CAPABILITIES

# Capabilities that delete/replace content are DESTRUCTIVE; the rest are WRITE_LOCAL.
_DESTRUCTIVE = {"file.delete", "shell.run", "shell.command"}


class SandboxError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SandboxPolicy(CapabilityRuntimeModel):
    """Allowlist/denylist policy enforced at execution time."""

    write_roots: tuple[str, ...]
    denied_path_substrings: tuple[str, ...] = (
        ".ssh",
        ".aws",
        ".gnupg",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "secring",
        ".env",
        "\\windows\\",
        "/windows/",
        "system32",
        "program files",
        "appdata\\roaming\\microsoft\\crypto",
    )
    denied_command_substrings: tuple[str, ...] = (
        "rm -rf /",
        "rm -rf ~",
        "rm -rf .",
        "sudo rm",
        "mkfs",
        "format ",
        "del /f /s /q c:",
        "rd /s /q c:",
        "rmdir /s /q c:",
        "shutdown",
        "diskpart",
        "reg delete",
        ":(){",
        "> /dev/sd",
        "curl | sh",
        "iwr | iex",
        "invoke-expression",
        "-encodedcommand",
    )
    max_output_chars: int = Field(default=4000, ge=256, le=20000)
    max_write_bytes: int = Field(default=1_000_000, ge=1, le=20_000_000)
    timeout_seconds: int = Field(default=20, ge=1, le=120)

    @classmethod
    def user_profile_default(cls) -> SandboxPolicy:
        """Writable under common user-profile dirs; system + secrets denied."""
        home = Path.home()
        roots = [home / name for name in ("Documents", "Desktop", "Downloads", "Projects", "Marvex")]
        write_roots = tuple(str(path.resolve()) for path in roots)
        return cls(write_roots=write_roots)

    def is_path_allowed(self, target: Path) -> bool:
        try:
            resolved = target.resolve()
        except OSError:
            return False
        lowered = str(resolved).lower().replace("/", "\\") if "\\" in str(resolved) else str(resolved).lower()
        for bad in self.denied_path_substrings:
            if bad.replace("/", "\\") in lowered or bad in str(resolved).lower():
                return False
        for root in self.write_roots:
            root_path = Path(root)
            if resolved == root_path or root_path in resolved.parents:
                return True
        return False

    def is_command_allowed(self, command: str) -> bool:
        lowered = command.lower()
        return not any(bad in lowered for bad in self.denied_command_substrings)


def _success(request: CapabilityExecutionRequest, safe_result: dict[str, object]) -> CapabilityResultEnvelope:
    return CapabilityResultEnvelope(
        schema_version=request.schema_version,
        result_id=f"{request.request_id}:result",
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        capability_ref=request.proposal.capability_ref,
        status="succeeded",
        safe_result=safe_result,
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


def _denial(request: CapabilityExecutionRequest, *, code: str) -> CapabilityResultEnvelope:
    return CapabilityResultEnvelope(
        schema_version=request.schema_version,
        result_id=f"{request.request_id}:result",
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        capability_ref=request.proposal.capability_ref,
        status="denied",
        safe_result={"reason_code": code},
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


def _target(arguments: dict[str, object]) -> Path:
    raw = str(arguments.get("path") or "").strip()
    if not raw:
        raise SandboxError("sandbox.path_required")
    return Path(raw).expanduser()


class WriteFileExecutor(CapabilityRuntimeModel):
    """Approval-gated local file mutation (write/mkdir/delete) under SandboxPolicy."""

    policy: SandboxPolicy

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        capability = request.proposal.capability_ref.identifier
        try:
            if capability == "file.write":
                safe = self._write(request.arguments)
            elif capability == "file.mkdir":
                safe = self._mkdir(request.arguments)
            elif capability == "file.delete":
                safe = self._delete(request.arguments)
            else:
                return _denial(request, code="sandbox.unsupported_capability")
        except SandboxError as exc:
            return _denial(request, code=exc.code)
        except OSError as exc:
            return _denial(request, code=f"sandbox.os_error:{exc.errno}")
        return _success(request, safe)

    def _write(self, arguments: dict[str, object]) -> dict[str, object]:
        target = _target(arguments)
        if not self.policy.is_path_allowed(target):
            raise SandboxError("sandbox.write_denied")
        content = str(arguments.get("content") or "")
        data = content.encode("utf-8")
        if len(data) > self.policy.max_write_bytes:
            raise SandboxError("sandbox.content_too_large")
        if not self.policy.is_path_allowed(target.parent):
            raise SandboxError("sandbox.parent_denied")
        existed = target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "operation": "write",
            "path": str(target.resolve()),
            "created": not existed,
            "byte_length": len(data),
            "raw_content_persisted": False,
        }

    def _mkdir(self, arguments: dict[str, object]) -> dict[str, object]:
        target = _target(arguments)
        if not self.policy.is_path_allowed(target):
            raise SandboxError("sandbox.mkdir_denied")
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        return {"operation": "mkdir", "path": str(target.resolve()), "created": not existed}

    def _delete(self, arguments: dict[str, object]) -> dict[str, object]:
        target = _target(arguments)
        if not self.policy.is_path_allowed(target):
            raise SandboxError("sandbox.delete_denied")
        if not target.exists():
            raise SandboxError("sandbox.not_found")
        if target.is_dir():
            # Only delete empty directories — refuse recursive deletes.
            try:
                target.rmdir()
            except OSError as exc:
                raise SandboxError("sandbox.directory_not_empty") from exc
            return {"operation": "delete", "path": str(target.resolve()), "kind": "directory"}
        target.unlink()
        return {"operation": "delete", "path": str(target.resolve()), "kind": "file"}


class ShellExecutor(CapabilityRuntimeModel):
    """Approval-gated local shell execution under SandboxPolicy (timeout + caps)."""

    policy: SandboxPolicy

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        if request.proposal.capability_ref.identifier not in SHELL_CAPABILITIES:
            return _denial(request, code="sandbox.unsupported_capability")
        command = str(request.arguments.get("command") or "").strip()
        if not command:
            return _denial(request, code="sandbox.command_required")
        if not self.policy.is_command_allowed(command):
            return _denial(request, code="sandbox.command_denied")
        cwd_value = str(request.arguments.get("cwd") or "").strip()
        cwd: Path | None = None
        if cwd_value:
            cwd = Path(cwd_value).expanduser()
            if not self.policy.is_path_allowed(cwd) or not cwd.is_dir():
                return _denial(request, code="sandbox.cwd_denied")
        try:
            completed = subprocess.run(  # noqa: S602 — approval-gated, policy-checked shell tool
                command,
                shell=True,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=self.policy.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return _denial(request, code="sandbox.timeout")
        except OSError as exc:
            return _denial(request, code=f"sandbox.os_error:{exc.errno}")
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        cap = self.policy.max_output_chars
        return _success(
            request,
            {
                "operation": "shell",
                "exit_code": completed.returncode,
                "stdout_preview": stdout[:cap],
                "stderr_preview": stderr[:cap],
                "stdout_truncated": len(stdout) > cap,
                "stderr_truncated": len(stderr) > cap,
                "raw_command_persisted": False,
            },
        )


class SandboxToolSpec(CapabilityRuntimeModel):
    """Classification used by the orchestrator to mark sandbox proposals."""

    identifier: str
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    requires_approval: Literal[True] = True


def sandbox_tool_spec(identifier: str) -> SandboxToolSpec:
    if identifier not in SANDBOX_CAPABILITIES:
        raise SandboxError("sandbox.unknown_capability")
    side_effect = ToolSideEffectLevel.DESTRUCTIVE if identifier in _DESTRUCTIVE else ToolSideEffectLevel.WRITE_LOCAL
    return SandboxToolSpec(identifier=identifier, risk_level=ToolRiskLevel.HIGH, side_effect_level=side_effect)
