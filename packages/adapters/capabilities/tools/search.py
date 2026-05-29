"""Content-search tool (file.search) — substring search across files."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from ..files import FileCapabilityError, _bounded_int, _relative_to, _resolve
from .base import Tool, succeeded_result


class SearchFilesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = Field(..., description="Sandbox root directory (absolute).")
    path: str = Field(default=".", description="Directory to search, relative to the root.")
    query: str = Field(..., min_length=1, description="Substring to search for in file contents.")
    max_matches: int = Field(default=20, ge=1, le=100)


class SearchFilesTool(Tool):
    id: ClassVar[str] = "search"
    name: ClassVar[str] = "Search file contents"
    description: ClassVar[str] = "Search for a substring inside files under a directory and return matches with previews."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = SearchFilesParams
    ref_prefix: ClassVar[str] = "file."

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        root, target, _relative = _resolve(request.arguments, require_dir=True, default_path=".")
        query = str(request.arguments.get("query") or "").strip()
        if not query:
            raise FileCapabilityError("file.query_required")
        limit = _bounded_int(request.arguments.get("max_matches"), default=20, lower=1, upper=100)
        matches: list[dict[str, object]] = []
        for path in sorted(target.rglob("*")):
            if len(matches) >= limit:
                break
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            index = text.lower().find(query.lower())
            if index < 0:
                continue
            preview = text[max(0, index - 40) : index + len(query) + 40]
            matches.append({"path": _relative_to(root, path), "preview": preview[:160]})
        return succeeded_result(
            request,
            {
                "operation": "search",
                "path": _relative_to(root, target),
                "query_present": True,
                "match_count": len(matches),
                "matches": matches,
                "truncated": len(matches) >= limit,
            },
        )


__all__ = ["SearchFilesTool", "SearchFilesParams"]
