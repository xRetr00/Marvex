from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.connector_runtime import ConnectorCategory, ConnectorRef, SourceIngestionPolicy, SourceSyncMode
from packages.memory_tree_runtime import CanonicalSourceMetadata, MemoryTreeRuntime, canonicalize_source_document, chunk_document
from packages.memory_tree_runtime.search import MemorySearchFilters, MemorySemanticQuery
from packages.memory_tree_runtime.models import SourceConnectorKind, SourceTrustLevel, SourceType


def _runtime() -> MemoryTreeRuntime:
    connector = ConnectorRef(connector_id="connector.manual", category=ConnectorCategory.GENERIC_OAUTH)
    now = datetime.now(UTC)
    docs = []
    for source_id, title, body, source_type, captured_at in (
        (
            "source.browser",
            "Browser approvals",
            "Playwright browser automation needs page boundary permission before agent navigation and read workflows.",
            SourceType.DOCUMENT,
            now,
        ),
        (
            "source.email",
            "Email preference",
            "User cares about recent inbox summaries more than old archived account notes.",
            SourceType.EMAIL,
            now - timedelta(days=90),
        ),
    ):
        docs.append(
            canonicalize_source_document(
                metadata=CanonicalSourceMetadata(source_id=source_id, external_id=f"external.{source_id}", uri=f"local://{source_id}", title=title, connector_ref=connector, captured_at=captured_at),
                markdown_body=body,
                ingested_at=captured_at,
            )
        )
    chunks = tuple(chunk for doc in docs for chunk in chunk_document(doc, max_chars=300))
    # Enrich metadata after chunking through model copies so filters are tested without raw content persistence.
    chunks = (
        chunks[0].model_copy(update={"metadata": {**chunks[0].metadata, "entity": "Playwright", "topic": "browser-agent", "trust_level": SourceTrustLevel.USER_APPROVED.value, "source_type": SourceType.DOCUMENT.value, "captured_at": now.isoformat(), "hotness": "0.91"}}),
        chunks[1].model_copy(update={"metadata": {**chunks[1].metadata, "entity": "Inbox", "topic": "email", "trust_level": SourceTrustLevel.UNVERIFIED.value, "source_type": SourceType.EMAIL.value, "captured_at": (now - timedelta(days=90)).isoformat(), "hotness": "0.44"}}),
    )
    return MemoryTreeRuntime.with_documents(documents=tuple(docs), chunks=chunks)


def test_semantic_memory_search_retrieves_related_memory_without_exact_keyword() -> None:
    result = _runtime().semantic_memory_search(MemorySemanticQuery(query="web agent permission", max_results=2))

    assert result.results
    assert result.results[0].evidence_links[0].source_id == "source.browser"
    assert result.search_mode == "local_semantic"
    assert result.results[0].safe_projection()["evidence_count"] >= 1


def test_memory_search_filters_by_trust_topic_source_type_hotness_and_recency() -> None:
    result = _runtime().semantic_memory_search(
        MemorySemanticQuery(
            query="recent account summaries",
            filters=MemorySearchFilters(trust_levels=(SourceTrustLevel.USER_APPROVED,), topics=("browser-agent",), source_types=(SourceType.DOCUMENT,), min_hotness=0.8, max_age_days=30, evidence_required=True),
        )
    )

    assert len(result.results) == 1
    assert result.results[0].evidence_links[0].source_id == "source.browser"
    assert result.filters_applied.trust_levels == (SourceTrustLevel.USER_APPROVED,)
