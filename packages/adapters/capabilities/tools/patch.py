"""Patch-file tool (file.patch) — append to or replace within a file.

Used both directly and as the destination for write.py when a write targets an
existing file without explicit overwrite intent (append-via-patch, the chosen
default for the B1 file.exists case).
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result
from ._write_support import ensure_parent, resolve_write_target, validated_content


class PatchFileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = Field(..., description="Sandbox root directory (absolute).")
    path: str = Field(..., description="File path relative to the root.")
    content: str = Field(..., description="Text to add to the file.")
    mode: Literal["append", "replace"] = Field(
        default="append",
        description="'append' adds to the end (default); 'replace' overwrites the whole file.",
    )


class PatchFileTool(Tool):
    id: ClassVar[str] = "patch"
    name: ClassVar[str] = "Patch file"
    description: ClassVar[str] = "Append text to an existing file (or replace its contents)."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.MEDIUM
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.WRITE_LOCAL
    params_model: ClassVar[type[BaseModel]] = PatchFileParams
    ref_prefix: ClassVar[str] = "file."

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        root, target, relative = resolve_write_target(request.arguments)
        content, encoded = validated_content(request.arguments)
        mode = str(request.arguments.get("mode") or "append").strip().lower()
        ensure_parent(root, target)
        existed = target.exists()
        if mode == "replace" or not existed:
            target.write_text(content, encoding="utf-8")
            operation = "replace" if existed else "create"
        else:
            existing = target.read_text(encoding="utf-8", errors="replace")
            separator = "" if existing.endswith("\n") or not existing else "\n"
            target.write_text(existing + separator + content, encoding="utf-8")
            operation = "append"
        return succeeded_result(
            request,
            {
                "operation": "patch",
                "patch_mode": operation,
                "path": relative,
                "bytes_added": len(encoded),
                "created": not existed,
                "raw_content_persisted": False,
            },
        )


__all__ = ["PatchFileTool", "PatchFileParams"]
