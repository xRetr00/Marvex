from __future__ import annotations

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
        capability_id = request.proposal.capability_ref.identifier
        if capability_id == "file.read":
            safe_result = self._read(request.arguments)
        elif capability_id == "file.list":
            safe_result = self._list(request.arguments)
        elif capability_id == "file.search":
            safe_result = self._search(request.arguments)
        else:
            raise FileCapabilityError("file.unsupported_capability")
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
