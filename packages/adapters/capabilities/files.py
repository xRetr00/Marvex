from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import Field

from packages.capability_runtime import CapabilityExecutionRequest, CapabilityKind, CapabilityRef, CapabilityResultEnvelope
from packages.capability_runtime.models import CapabilityRuntimeModel


class FileCapabilityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReadOnlyFileExecutor(CapabilityRuntimeModel):
    max_preview_chars: int = Field(default=1200, ge=1, le=4000)
    max_entries: int = Field(default=50, ge=1, le=200)
    max_matches: int = Field(default=20, ge=1, le=100)

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        # Delegates to the per-file read tools (docs/TODO/07). Scoped to the
        # read-only set so this executor can NEVER perform a write, regardless
        # of the requested capability id.
        capability_id = request.proposal.capability_ref.identifier
        if capability_id not in {"file.read", "file.list", "file.search", "file.rg"}:
            raise FileCapabilityError("file.unsupported_capability")
        from packages.adapters.capabilities.tools import (
            ListDirectoryTool,
            ReadFileTool,
            RipgrepTool,
            SearchFilesTool,
            ToolRegistry,
        )

        registry = ToolRegistry(
            (ReadFileTool(), ListDirectoryTool(), SearchFilesTool(), RipgrepTool())
        )
        return registry.execute(request)

    def denial_result(
        self,
        request: CapabilityExecutionRequest,
        *,
        code: str,
    ) -> CapabilityResultEnvelope:
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

    def _read(self, arguments: dict[str, object]) -> dict[str, object]:
        root, target, relative = _resolve(arguments, require_file=True)
        limit = _bounded_int(arguments.get("max_preview_chars"), default=self.max_preview_chars, lower=1, upper=4000)
        text = target.read_text(encoding="utf-8", errors="replace")
        preview = text[:limit]
        return {
            "operation": "read",
            "root_configured": bool(root),
            "path": relative,
            "preview": preview,
            "truncated": len(text) > len(preview),
            "byte_length": target.stat().st_size,
        }

    def _list(self, arguments: dict[str, object]) -> dict[str, object]:
        _root, target, relative = _resolve(arguments, require_dir=True)
        limit = _bounded_int(arguments.get("max_entries"), default=self.max_entries, lower=1, upper=200)
        entries = sorted(path.name for path in target.iterdir())[:limit]
        total = sum(1 for _ in target.iterdir())
        return {
            "operation": "list",
            "path": relative,
            "entries": entries,
            "entry_count": len(entries),
            "truncated": total > len(entries),
        }

    def _search(self, arguments: dict[str, object]) -> dict[str, object]:
        root, target, _relative = _resolve(arguments, require_dir=True, default_path=".")
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise FileCapabilityError("file.query_required")
        limit = _bounded_int(arguments.get("max_matches"), default=self.max_matches, lower=1, upper=100)
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
        return {
            "operation": "search",
            "path": _relative_to(root, target),
            "query_present": True,
            "match_count": len(matches),
            "matches": matches,
            "truncated": len(matches) >= limit,
        }

    def _rg(self, arguments: dict[str, object]) -> dict[str, object]:
        root, target, _relative = _resolve(arguments, require_dir=True, default_path=".")
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise FileCapabilityError("file.query_required")
        limit = _bounded_int(arguments.get("max_matches"), default=self.max_matches, lower=1, upper=100)
        rg = shutil.which("rg")
        matches = _rg_file_matches(root, target, query=query, limit=limit, rg=rg)
        return {
            "operation": "rg",
            "path": _relative_to(root, target),
            "query_present": True,
            "match_count": len(matches),
            "matches": matches,
            "truncated": len(matches) >= limit,
            "backend": "ripgrep" if rg else "python_fallback",
        }


def file_capability_ref(identifier: str) -> CapabilityRef:
    return CapabilityRef(kind=CapabilityKind.TOOL, identifier=identifier)


def _resolve(
    arguments: dict[str, object],
    *,
    require_file: bool = False,
    require_dir: bool = False,
    default_path: str | None = None,
) -> tuple[Path, Path, str]:
    root_value = str(arguments.get("root") or "").strip()
    if not root_value:
        raise FileCapabilityError("file.root_required")
    root = Path(root_value).resolve()
    if not root.is_dir():
        raise FileCapabilityError("file.root_unavailable")
    relative_value = str(arguments.get("path") or default_path or "").strip()
    if not relative_value:
        raise FileCapabilityError("file.path_required")
    target = (root / relative_value).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise FileCapabilityError("file.sandbox_violation") from exc
    if require_file and not target.is_file():
        raise FileCapabilityError("file.not_found")
    if require_dir and not target.is_dir():
        raise FileCapabilityError("file.not_directory")
    return root, target, _relative_to(root, target)


def _relative_to(root: Path, target: Path) -> str:
    value = target.relative_to(root).as_posix()
    return "." if value == "." else value


def _bounded_int(value: object, *, default: int, lower: int, upper: int) -> int:
    if isinstance(value, int):
        return max(lower, min(upper, value))
    return default


def _rg_file_matches(root: Path, target: Path, *, query: str, limit: int, rg: str | None) -> list[dict[str, object]]:
    tokens = tuple(token for token in re_split_query(query) if token)
    if rg:
        try:
            completed = subprocess.run(
                [rg, "--files", "--hidden", "--glob", "!**/.git/**"],
                cwd=target,
                text=True,
                capture_output=True,
                timeout=8,
            )
            if completed.returncode in {0, 1}:
                return _filter_path_lines(root, target, completed.stdout.splitlines(), tokens=tokens, limit=limit)
        except Exception:
            pass
    lines = [path.relative_to(target).as_posix() for path in sorted(target.rglob("*")) if path.is_file()]
    return _filter_path_lines(root, target, lines, tokens=tokens, limit=limit)


# Common request/verb words that are never useful as filename-match tokens.
# Filtering these lets a natural request like "read the contents of the my uni
# report on desktop" match "...University_Report.pdf" instead of failing because
# "read"/"contents"/"tell" aren't in the filename. This is a phrasing-robust
# ranking change, not a per-phrase keyword list.
_FILENAME_STOPWORDS = frozenset(
    {
        "the", "a", "an", "of", "on", "in", "at", "to", "into", "my", "me",
        "your", "this", "that", "those", "these", "it", "is", "are", "and",
        "or", "for", "from", "with", "please", "read", "open", "show", "tell",
        "give", "get", "find", "search", "look", "contents", "content", "file",
        "files", "how", "good", "bad", "what", "which", "where", "see", "view",
        "desktop", "documents", "downloads", "folder", "directory", "drive",
        "disk", "named", "called", "about",
    }
)


def re_split_query(query: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in query.replace(".", " ").replace("_", " ").replace("-", " ").split())


def _content_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Drop stopwords; keep meaningful filename tokens (length >= 2)."""

    return tuple(t for t in tokens if len(t) >= 2 and t not in _FILENAME_STOPWORDS)


def _filter_path_lines(root: Path, target: Path, lines: list[str], *, tokens: tuple[str, ...], limit: int) -> list[dict[str, object]]:
    content_tokens = _content_tokens(tokens)
    # Fall back to raw tokens only if every token was a stopword, so an
    # all-stopword query still requires >=1 match instead of returning the
    # whole directory. An empty query (no tokens at all) keeps list-all.
    match_tokens = content_tokens or tokens
    scored: list[tuple[int, dict[str, object]]] = []
    for line in lines:
        candidate = line.strip().replace("\\", "/")
        if not candidate:
            continue
        searchable = candidate.lower().replace(".", " ").replace("_", " ").replace("-", " ")
        if match_tokens:
            # Rank by how many meaningful tokens appear in the path; require at
            # least one. (Old behaviour required ALL raw tokens to match, so a
            # full-sentence query never matched a real filename.)
            score = sum(1 for token in match_tokens if token in searchable)
            if score == 0:
                continue
        else:
            score = 0
        resolved = (target / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        scored.append((score, {"path": _relative_to(root, resolved), "name": resolved.name}))
    # Highest token overlap first; stable order preserved for ties.
    scored.sort(key=lambda item: item[0], reverse=True)
    return [match for _score, match in scored[:limit]]


class SandboxedFileWriteExecutor(CapabilityRuntimeModel):
    max_content_bytes: int = Field(default=16_384, ge=1, le=65_536)

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        # Delegates to the per-file write/patch tools (docs/TODO/07). The old
        # hard `file.exists` failure is replaced by append-via-patch when a
        # write targets an existing file without explicit overwrite intent
        # (see WriteFileTool); explicit overwrite still replaces.
        from packages.adapters.capabilities.tools import (
            PatchFileTool,
            ToolRegistry,
            WriteFileTool,
        )

        registry = ToolRegistry((WriteFileTool(), PatchFileTool()))
        capability_id = request.proposal.capability_ref.identifier
        if registry.get(capability_id) is None:
            # Backwards compatibility: this executor historically only handled
            # file.write; treat any other id as a write request.
            from packages.capability_runtime import CapabilityKind, CapabilityRef

            request = request.model_copy(
                update={
                    "proposal": request.proposal.model_copy(
                        update={
                            "capability_ref": CapabilityRef(
                                kind=CapabilityKind.TOOL, identifier="file.write"
                            )
                        }
                    )
                }
            )
        return registry.execute(request)
