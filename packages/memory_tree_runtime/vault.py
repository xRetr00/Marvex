from __future__ import annotations

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
