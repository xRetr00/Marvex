"""List-directory tool (file.list)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from ..files import _bounded_int, _resolve
from .base import Tool, succeeded_result


class ListDirectoryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = Field(..., description="Sandbox root directory (absolute).")
    path: str = Field(..., description="Directory path relative to the root.")
    max_entries: int = Field(default=50, ge=1, le=200)


class ListDirectoryTool(Tool):
    id: ClassVar[str] = "list"
    name: ClassVar[str] = "List directory"
    description: ClassVar[str] = "List the file and folder names in a directory."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = ListDirectoryParams
    ref_prefix: ClassVar[str] = "file."

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        _root, target, relative = _resolve(request.arguments, require_dir=True)
        limit = _bounded_int(request.arguments.get("max_entries"), default=50, lower=1, upper=200)
        entries = sorted(path.name for path in target.iterdir())[:limit]
        total = sum(1 for _ in target.iterdir())
        return succeeded_result(
            request,
            {
                "operation": "list",
                "path": relative,
                "entries": entries,
                "entry_count": len(entries),
                "truncated": total > len(entries),
            },
        )


__all__ = ["ListDirectoryTool", "ListDirectoryParams"]
