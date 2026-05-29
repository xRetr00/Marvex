"""Filename-search tool (file.rg) — find files by name tokens via ripgrep."""

from __future__ import annotations

import shutil
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from ..files import FileCapabilityError, _bounded_int, _relative_to, _resolve, _rg_file_matches
from .base import Tool, succeeded_result


class RipgrepParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = Field(..., description="Sandbox root directory (absolute).")
    path: str = Field(default=".", description="Directory to search, relative to the root.")
    query: str = Field(..., min_length=1, description="Filename tokens to match (e.g. 'uni report pdf').")
    max_matches: int = Field(default=20, ge=1, le=100)


class RipgrepTool(Tool):
    id: ClassVar[str] = "rg"
    name: ClassVar[str] = "Find files by name"
    description: ClassVar[str] = "Find files whose path matches the given name tokens (ripgrep-backed, python fallback)."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = RipgrepParams
    ref_prefix: ClassVar[str] = "file."

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        root, target, _relative = _resolve(request.arguments, require_dir=True, default_path=".")
        query = str(request.arguments.get("query") or "").strip()
        if not query:
            raise FileCapabilityError("file.query_required")
        limit = _bounded_int(request.arguments.get("max_matches"), default=20, lower=1, upper=100)
        rg = shutil.which("rg")
        matches = _rg_file_matches(root, target, query=query, limit=limit, rg=rg)
        return succeeded_result(
            request,
            {
                "operation": "rg",
                "path": _relative_to(root, target),
                "query_present": True,
                "match_count": len(matches),
                "matches": matches,
                "truncated": len(matches) >= limit,
                "backend": "ripgrep" if rg else "python_fallback",
            },
        )


__all__ = ["RipgrepTool", "RipgrepParams"]
