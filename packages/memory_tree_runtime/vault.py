from __future__ import annotations

from pathlib import Path

from .models import CanonicalMemoryDocument


def project_document_to_vault_markdown(document: CanonicalMemoryDocument) -> str:
    safe_title = document.metadata.title.replace("---", "-")
    return (
        "---\n"
        f"document_id: {document.document_id}\n"
        f"source_id: {document.metadata.source_id}\n"
        f"external_id: {document.metadata.external_id}\n"
        f"title: {safe_title}\n"
        "raw_secret_persisted: false\n"
        "---\n\n"
        f"{document.normalized_markdown}\n"
    )


def write_document_to_obsidian_vault(*, vault_root: str | Path, document: CanonicalMemoryDocument) -> Path:
    wiki = Path(vault_root).expanduser().resolve() / "wiki"
    summaries = wiki / "summaries"
    notes = wiki / "notes"
    summaries.mkdir(parents=True, exist_ok=True)
    notes.mkdir(parents=True, exist_ok=True)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(document.metadata.title) + ".md"
    path = summaries / filename
    path.write_text(project_document_to_vault_markdown(document), encoding="utf-8")
    return path


def read_manual_notes_from_obsidian_vault(*, vault_root: str | Path, max_notes: int = 20) -> tuple[tuple[str, str], ...]:
    notes = Path(vault_root).expanduser().resolve() / "wiki" / "notes"
    if not notes.exists():
        return ()
    rows: list[tuple[str, str]] = []
    for path in sorted(notes.glob("*.md"))[: max(1, max_notes)]:
        text = path.read_text(encoding="utf-8")
        body = _strip_frontmatter(text).strip()
        if body:
            rows.append((path.stem, body[:1200]))
    return tuple(rows)


def _safe_filename(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-_ ." else "-" for character in value).strip()
    return safe or "memory"


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    parts = text.split("---\n", 2)
    return parts[2] if len(parts) == 3 else text
