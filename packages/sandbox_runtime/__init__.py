"""Marvex policy sandbox runtime.

Real local-FS write + shell execution for the agent, gated by CapabilityRuntime
approval and constrained by a SandboxPolicy (path allowlist, secret/system
denylist, destructive-command denylist, timeouts, output caps). This lives in
its own runtime package — not the bounded `packages/adapters/capabilities`
seam layer — because it performs real execution (subprocess + filesystem).
"""
from __future__ import annotations

from packages.sandbox_runtime.sandbox import (
    SANDBOX_CAPABILITIES,
    SHELL_CAPABILITIES,
    WRITE_CAPABILITIES,
    SandboxError,
    SandboxPolicy,
    SandboxToolSpec,
    ShellExecutor,
    WriteFileExecutor,
    sandbox_tool_spec,
)

__all__ = [
    "SANDBOX_CAPABILITIES",
    "SHELL_CAPABILITIES",
    "WRITE_CAPABILITIES",
    "SandboxError",
    "SandboxPolicy",
    "SandboxToolSpec",
    "ShellExecutor",
    "WriteFileExecutor",
    "sandbox_tool_spec",
]
