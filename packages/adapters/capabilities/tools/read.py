"""Read-file tool (file.read).

Reads a sandboxed text or PDF file and returns a bounded preview. PDF support
(via pypdf, already a dependency) addresses the field case where reading a
named report on the Desktop returned nothing because the reader was text-only.
"""

from __future__ import annotations

import shutil
from pathlib import Path
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


class ReadFileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = Field(..., description="Sandbox root directory (absolute).")
    path: str = Field(..., description="File path relative to the root.")
    max_preview_chars: int = Field(default=1200, ge=1, le=4000)


class ReadFileTool(Tool):
    id: ClassVar[str] = "read"
    name: ClassVar[str] = "Read file"
    description: ClassVar[str] = "Read the contents of a text or PDF file and return a bounded preview."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = ReadFileParams
    ref_prefix: ClassVar[str] = "file."

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        root, target, relative, resolution = _resolve_read_target(request.arguments)
        limit = _bounded_int(
            request.arguments.get("max_preview_chars"), default=1200, lower=1, upper=4000
        )
        if target.suffix.lower() == ".pdf":
            text, kind = _read_pdf_text(target), "pdf"
        else:
            text, kind = target.read_text(encoding="utf-8", errors="replace"), "text"
        preview = text[:limit]
        return succeeded_result(
            request,
            {
                "operation": "read",
                "root_configured": bool(root),
                "path": relative,
                "kind": kind,
                "preview": preview,
                "truncated": len(text) > len(preview),
                "byte_length": target.stat().st_size,
                **resolution,
            },
        )


def _resolve_read_target(arguments: dict[str, object]) -> tuple[Path, Path, str, dict[str, object]]:
    try:
        root, target, relative = _resolve(arguments, require_file=True)
        return root, target, relative, {
            "resolved_by_search": False,
            "resolution_match_count": 0,
            "resolution_candidates": [],
        }
    except FileCapabilityError as exc:
        if exc.code != "file.not_found":
            raise
        missing = exc

    root, target, _relative = _resolve(arguments, default_path=".")
    path_query = str(arguments.get("path") or "").strip()
    natural_query = str(arguments.get("natural_query") or "").strip()
    query = natural_query or path_query
    if not path_query and not query:
        raise missing
    path_value = path_query.replace("\\", "/")
    parent_value = str(Path(path_value).parent)
    file_query = query
    search_dir = target if target.is_dir() else root
    if parent_value not in {"", "."} and not target.is_dir():
        candidate_dir = (root / parent_value).resolve()
        try:
            candidate_dir.relative_to(root)
        except ValueError as exc:
            raise FileCapabilityError("file.sandbox_violation") from exc
        if candidate_dir.is_dir():
            search_dir = candidate_dir
    matches = _rg_file_matches(root, search_dir, query=file_query, limit=5, rg=shutil.which("rg"))
    for match in matches:
        candidate_path = str(match.get("path") or "")
        candidate = (root / candidate_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return root, candidate, _relative_to(root, candidate), {
                "resolved_by_search": True,
                "resolution_match_count": len(matches),
                "resolution_candidates": [str(item.get("path") or "") for item in matches[:5]],
            }
    raise missing


def _read_pdf_text(target: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency missing
        raise FileCapabilityError("file.pdf_reader_unavailable") from exc
    try:
        reader = PdfReader(str(target))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise FileCapabilityError("file.pdf_unreadable") from exc


__all__ = ["ReadFileTool", "ReadFileParams"]
