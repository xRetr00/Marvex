from datetime import UTC, datetime


def _document():
    from packages.connector_runtime import ConnectorCategory, ConnectorRef
    from packages.memory_tree_runtime import CanonicalSourceMetadata, canonicalize_source_document

    metadata = CanonicalSourceMetadata(
        source_id="source-github",
        external_id="issue-1",
        uri="github://issues/1",
        title="Memory Tree Issue",
        connector_ref=ConnectorRef(connector_id="github-primary", category=ConnectorCategory.GITHUB),
        captured_at=datetime(2026, 5, 18, tzinfo=UTC),
    )
    return canonicalize_source_document(
        metadata=metadata,
        markdown_body="Memory tree should expose source grounded evidence and daily digest summaries.",
        ingested_at=datetime(2026, 5, 18, tzinfo=UTC),
    )


def test_sqlite_memory_tree_index_persists_sources_documents_chunks_scores_and_nodes(tmp_path):
    from packages.memory_tree_runtime import EvidenceLink, MemoryTreeNode, SQLiteMemoryTreeIndex, chunk_document, score_memory_chunk

    index = SQLiteMemoryTreeIndex(memory_db_path=tmp_path / "tree.db", local_user_root=tmp_path)
    document = _document()
    chunks = chunk_document(document, max_chars=40)
    score = score_memory_chunk(chunk_id=chunks[0].chunk_id, source_weight=0.9, recency=0.8, interaction=0.4, entity_topic_boost=0.1)
    node = MemoryTreeNode.summary_node(
        node_id="node-source-root",
        title="GitHub summary",
        summary="Memory tree evidence exists.",
        evidence_links=(EvidenceLink(document_id=document.document_id, chunk_id=chunks[0].chunk_id, source_id=document.metadata.source_id, quote_preview="Memory tree should expose"),),
    )

    index.upsert_document(document)
    index.upsert_chunks(chunks)
    index.upsert_score(score)
    index.upsert_node(node, tree_kind="source", tree_key=document.metadata.source_id)

    assert index.safe_sources()[0]["source_id"] == "source-github"
    assert index.safe_documents()[0]["title"] == "Memory Tree Issue"
    assert index.safe_chunks()[0]["document_id"] == document.document_id
    assert index.safe_scores()[0]["decision"] == "keep"
    assert index.safe_scores()[0]["source_weight"] == 0.9
    tree_node = index.safe_tree_nodes(tree_kind="source", tree_key="source-github")[0]
    assert tree_node["evidence_count"] == 1
    assert tree_node["evidence_links"][0]["chunk_id"] == chunks[0].chunk_id
    forget = index.forget_source("source-github")
    assert forget.safe_projection()["documents_deleted"] == 1
    assert forget.safe_projection()["chunks_deleted"] == len(chunks)
    assert index.safe_sources() == ()
    assert index.safe_tree_nodes(tree_kind="source", tree_key="source-github") == ()


def test_memory_traversal_tools_return_source_grounded_evidence():
    from packages.memory_tree_runtime import MemoryTreeRuntime, SQLiteMemoryTreeIndex, chunk_document

    document = _document()
    chunks = chunk_document(document, max_chars=80)
    runtime = MemoryTreeRuntime.with_documents(documents=(document,), chunks=chunks)

    search = runtime.memory_tree_search("daily digest evidence")
    query = runtime.memory_query_with_evidence("source grounded")
    source_tree = runtime.memory_get_source_tree("source-github")
    digest = runtime.memory_get_daily_digest("2026-05-18")
    drill = runtime.memory_drill_down(chunks[0].chunk_id)

    assert search.results[0].evidence_links
    assert search.safe_projection()["results"][0]["evidence_links"][0]["source_id"] == "source-github"
    assert query.results[0].evidence_links[0].source_id == "source-github"
    assert source_tree.root.evidence_links
    assert digest.evidence_links
    assert drill.chunk_id == chunks[0].chunk_id
    assert "raw" not in repr(search.safe_projection()).lower()
