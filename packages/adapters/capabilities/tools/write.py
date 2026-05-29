"""Write-file tool (file.write).

Overwrite semantics (chosen default — see docs/TODO/07, B1):
* file does not exist        -> create it
* exists + overwrite=True    -> replace contents (explicit user intent)
* exists + overwrite=False   -> APPEND the new content (append-via-patch),
                                never silently destroying the existing file.

This removes the old hard `file.exists` failure that made "create a file" on an
existing name error out.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result
from ._write_support import ensure_parent, resolve_write_target, validated_content


class WriteFileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = Field(..., description="Sandbox root directory (absolute).")
    path: str = Field(..., description="File path relative to the root.")
    content: str = Field(..., description="Text content to write.")
    overwrite: bool = Field(
        default=False,
        description="If true, replace an existing file. If false and the file exists, the content is appended.",
    )


class WriteFileTool(Tool):
    id: ClassVar[str] = "write"
    name: ClassVar[str] = "Write file"
    description: ClassVar[str] = "Write text to a file. Creates it if missing; appends if it exists unless overwrite is set."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.MEDIUM
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.WRITE_LOCAL
    params_model: ClassVar[type[BaseModel]] = WriteFileParams
    ref_prefix: ClassVar[str] = "file."

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        root, target, relative = resolve_write_target(request.arguments)
        content, encoded = validated_content(request.arguments)
        overwrite = bool(request.arguments.get("overwrite", False))
        ensure_parent(root, target)
        existed = target.exists()
        if not existed:
            target.write_text(content, encoding="utf-8")
            operation = "create"
        elif overwrite:
            target.write_text(content, encoding="utf-8")
            operation = "overwrite"
        else:
            # Append-via-patch: never destroy existing content without explicit
            # overwrite intent.
            existing = target.read_text(encoding="utf-8", errors="replace")
            separator = "" if existing.endswith("\n") or not existing else "\n"
            target.write_text(existing + separator + content, encoding="utf-8")
            operation = "append"
        return succeeded_result(
            request,
            {
                "operation": "write",
                "write_mode": operation,
                "path": relative,
                "bytes_written": len(encoded),
                "created": not existed,
                "overwritten": existed and overwrite,
                "appended": existed and not overwrite,
                "raw_content_persisted": False,
            },
        )


__all__ = ["WriteFileTool", "WriteFileParams"]
