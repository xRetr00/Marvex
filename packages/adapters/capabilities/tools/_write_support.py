"""Shared sandboxed write/append helpers for write.py and patch.py."""

from __future__ import annotations

from pathlib import Path

from ..files import FileCapabilityError, _resolve

MAX_CONTENT_BYTES = 16_384


def resolve_write_target(arguments: dict[str, object]) -> tuple[Path, Path, str]:
    """Resolve a sandboxed write target (no require_file/dir)."""

    return _resolve(arguments)


def validated_content(arguments: dict[str, object]) -> tuple[str, bytes]:
    content = arguments.get("content")
    if not isinstance(content, str):
        raise FileCapabilityError("file.content_required")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_CONTENT_BYTES:
        raise FileCapabilityError("file.content_too_large")
    return content, encoded


def ensure_parent(root: Path, target: Path) -> None:
    if target.parent != root and not target.parent.exists():
        raise FileCapabilityError("file.parent_missing")


__all__ = [
    "MAX_CONTENT_BYTES",
    "resolve_write_target",
    "validated_content",
    "ensure_parent",
]
