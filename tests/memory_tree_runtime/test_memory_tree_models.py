from datetime import UTC, datetime

from pydantic import ValidationError


def test_memory_source_policy_defaults_to_no_hidden_sync_and_safe_projection():
    from packages.connector_runtime import SourceIngestionPolicy, SourceSyncInterval, SourceSyncMode
    from packages.memory_tree_runtime import (
        MemorySourceRef,
        SourceConnectorKind,
        SourcePermissionScope,
        SourceProvenance,
        SourceTrustLevel,
        SourceType,
    )

    source = MemorySourceRef(
        source_id="source-github-issues",
        source_type=SourceType.REPOSITORY,
        connector_kind=SourceConnectorKind.GITHUB,
        provenance=SourceProvenance.USER_CONNECTED_ACCOUNT,
        trust_level=SourceTrustLevel.USER_APPROVED,
        permission_scope=SourcePermissionScope.READ_ONLY_METADATA_AND_CONTENT,
        ingestion_policy=SourceIngestionPolicy(
            sync_mode=SourceSyncMode.DISABLED,
            interval=SourceSyncInterval.MANUAL_ONLY,
            auto_fetch_enabled=False,
            human_approved=True,
        ),
        display_name="GitHub Issues",
    )

    projection = source.safe_projection()
    assert projection["source_id"] == "source-github-issues"
    assert projection["ingestion_policy"]["auto_fetch_enabled"] is False
    assert projection["raw_credentials_persisted"] is False


def test_canonical_document_normalizes_markdown_and_rejects_secret_like_content():
    from packages.connector_runtime import ConnectorCategory, ConnectorRef
    from packages.memory_tree_runtime import CanonicalMemoryDocument, CanonicalSourceMetadata, canonicalize_source_document

    connector_ref = ConnectorRef(connector_id="notion-primary", category=ConnectorCategory.NOTION)
    metadata = CanonicalSourceMetadata(
        source_id="source-notion",
        external_id="page-1",
        uri="notion://page/page-1",
        title="Project Notes",
        connector_ref=connector_ref,
        captured_at=datetime(2026, 5, 18, tzinfo=UTC),
    )

    document = canonicalize_source_document(
        metadata=metadata,
        markdown_body="  # Project Notes\r\n\r\nMarvex memory tree planning.\r\n  ",
        ingested_at=datetime(2026, 5, 18, tzinfo=UTC),
    )

    assert isinstance(document, CanonicalMemoryDocument)
    assert document.document_id.startswith("cmdoc:")
    assert document.normalized_markdown == "# Project Notes\n\nMarvex memory tree planning."
    assert document.raw_secret_persisted is False

    with pytest_raises_validation():
        canonicalize_source_document(
            metadata=metadata,
            markdown_body="Authorization: Bearer abc123",
            ingested_at=datetime(2026, 5, 18, tzinfo=UTC),
        )


def test_chunking_bounds_content_links_to_document_and_marks_duplicates():
    from packages.connector_runtime import ConnectorCategory, ConnectorRef
    from packages.memory_tree_runtime import CanonicalSourceMetadata, canonicalize_source_document, chunk_document

    metadata = CanonicalSourceMetadata(
        source_id="source-drive",
        external_id="doc-1",
        uri="gdrive://doc/doc-1",
        title="Drive Doc",
        connector_ref=ConnectorRef(connector_id="drive-primary", category=ConnectorCategory.GOOGLE_DRIVE),
        captured_at=datetime(2026, 5, 18, tzinfo=UTC),
    )
    document = canonicalize_source_document(
        metadata=metadata,
        markdown_body="Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu.",
        ingested_at=datetime(2026, 5, 18, tzinfo=UTC),
    )

    chunks = chunk_document(document, max_chars=28)

    assert len(chunks) >= 2
    assert all(chunk.document_id == document.document_id for chunk in chunks)
    assert all(len(chunk.markdown) <= 28 for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    assert chunks[0].duplicate_ready_hash == chunks[0].content_hash


def test_scoring_explains_keep_drop_without_external_policy_ownership():
    from packages.memory_tree_runtime import score_memory_chunk

    score = score_memory_chunk(
        chunk_id="chunk:source:1",
        source_weight=0.8,
        recency=0.6,
        interaction=0.4,
        entity_topic_boost=0.2,
    )

    assert score.importance.value == 0.62
    assert score.keep_drop_decision.decision == "keep"
    projection = score.safe_projection()
    assert projection["source_weight"] == 0.8
    assert projection["recency"] == 0.6
    assert projection["raw_content_persisted"] is False
    assert score.explanation.policy_owner == "MemoryTreeRuntime"


def test_memory_trees_require_evidence_and_traversal_returns_safe_results():
    from packages.memory_tree_runtime import EvidenceLink, MemoryTreeNode, SourceMemoryTree, TreeTraversalResult, traverse_tree

    evidence = EvidenceLink(document_id="cmdoc:abc", chunk_id="chunk:abc:0", source_id="source-github", quote_preview="Issue mentions memory tree.")
    root = MemoryTreeNode.summary_node(
        node_id="node-source-root",
        title="GitHub source summary",
        summary="Source includes memory tree planning.",
        evidence_links=(evidence,),
    )
    tree = SourceMemoryTree(source_id="source-github", root=root, nodes=(root,))

    result = traverse_tree(tree, start_node_id="node-source-root", max_depth=2)

    assert isinstance(result, TreeTraversalResult)
    assert result.nodes[0].evidence_links[0].chunk_id == "chunk:abc:0"
    node_projection = result.safe_projection()["nodes"][0]
    assert node_projection["evidence_count"] == 1
    assert node_projection["evidence_links"][0]["source_id"] == "source-github"

    with pytest_raises_validation():
        MemoryTreeNode.summary_node(node_id="node-empty", title="Bad", summary="No provenance", evidence_links=())


class pytest_raises_validation:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            raise AssertionError("expected validation error")
        return issubclass(exc_type, ValidationError)

def test_memory_tree_telemetry_summary_is_counts_only():
    from packages.memory_tree_runtime import MemoryTreeTelemetrySummary

    summary = MemoryTreeTelemetrySummary(
        event_kind="tree_updated",
        documents_canonicalized=1,
        chunks_created=2,
        scores_created=2,
        tree_nodes_updated=3,
        traversal_results=0,
    )

    projection = summary.safe_projection()
    assert projection["tree_nodes_updated"] == 3
    assert projection["raw_content_persisted"] is False
    assert "markdown" not in repr(projection).lower()
