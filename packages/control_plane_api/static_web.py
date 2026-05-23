from __future__ import annotations

from pathlib import Path

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
    ".txt": "text/plain; charset=utf-8",
}


def content_type_for(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def resolve_static_file(dist_root: Path, request_path: str) -> tuple[Path | None, str]:
    """Resolve a request path to a file inside ``dist_root``.

    Returns ``(path, content_type)``. Unknown SPA routes fall back to
    ``index.html``. Path traversal outside ``dist_root`` is rejected (also
    falls back to ``index.html``). ``path`` is ``None`` only when no index
    exists.
    """
    root = dist_root.resolve()
    index = root / "index.html"
    rel = request_path.lstrip("/")
    if not rel:
        return (index if index.is_file() else None, content_type_for(index))
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return (index if index.is_file() else None, content_type_for(index))
    if candidate.is_file():
        return candidate, content_type_for(candidate)
    return (index if index.is_file() else None, content_type_for(index))
