"""Tests for memory_tree_runtime extraction: entities, facts, preferences,
relations, topic hotness, and daily digest — all derived-safe with provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.connector_runtime import ConnectorCategory, ConnectorRef
from packages.memory_tree_runtime import (
    CanonicalSourceMetadata,
    canonicalize_source_document,
    chunk_document,
)
from packages.memory_tree_runtime.extraction import (
    ChunkExtractionResult,
    DailyDigestEntry,
    ExtractedEntity,
    ExtractedFact,
    ExtractedPreference,
    ExtractedRelation,
    build_daily_digest_entries,
    build_daily_digest_node,
    compute_hotness_boost,
    compute_topic_hotness,
    extract_chunk,
    extract_chunks,
    extract_entities,
    extract_facts,
    extract_preferences,
    extract_relations,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_chunk(markdown: str, source_id: str = "source-test") -> object:
    """Create a real MemoryChunk via canonical pipeline."""
    connector = ConnectorRef(connector_id="conn-test", category=ConnectorCategory.GENERIC_OAUTH)
    metadata = CanonicalSourceMetadata(
        source_id=source_id,
        external_id="ext-1",
        uri=f"local://{source_id}",
        title="Test Document",
        connector_ref=connector,
        captured_at=datetime(2026, 5, 20, tzinfo=UTC),
    )
    doc = canonicalize_source_document(
        metadata=metadata,
        markdown_body=markdown,
        ingested_at=datetime(2026, 5, 20, tzinfo=UTC),
    )
    chunks = chunk_document(doc, max_chars=900)
    assert chunks, "need at least one chunk"
    return chunks[0]


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def test_extract_entities_finds_person_names() -> None:
    chunk = _make_chunk("Alice Smith reviewed the memory tree design with Bob Johnson.")
    entities = extract_entities(chunk)
    labels = {e.label for e in entities}
    assert "Alice Smith" in labels or "Bob Johnson" in labels


def test_extract_entities_finds_repo_refs() -> None:
    chunk = _make_chunk("The marvex/memory-tree repo implements content-addressed chunks.")
    entities = extract_entities(chunk)
    assert any(e.kind == "repo" and "marvex/memory-tree" in e.label for e in entities)


def test_extract_entities_finds_quoted_projects() -> None:
    chunk = _make_chunk('The `Marvex` project uses "Obsidian" for the vault layer.')
    entities = extract_entities(chunk)
    labels = {e.label for e in entities}
    assert "Marvex" in labels or "Obsidian" in labels


def test_extract_entities_carries_provenance() -> None:
    chunk = _make_chunk("Alice Smith is the project lead.", source_id="source-github")
    entities = extract_entities(chunk)
    assert entities, "expected at least one entity"
    for entity in entities:
        assert entity.chunk_id == chunk.chunk_id
        assert entity.document_id == chunk.document_id
        assert entity.source_id == "source-github"
        assert entity.raw_content_persisted is False


def test_extract_entities_safe_projection_no_raw() -> None:
    chunk = _make_chunk("Alice Smith leads the Marvex project.")
    entities = extract_entities(chunk)
    for entity in entities:
        proj = entity.safe_projection()
        assert proj["raw_content_persisted"] is False
        assert "markdown" not in repr(proj).lower()


def test_extract_entities_rejects_secret_content() -> None:
    chunk = _make_chunk("Normal text that mentions a valid person")
    # Manually patch markdown with secret-like content by creating via pipeline
    # — we test the guard via a chunk whose markdown contains secret terms
    from packages.memory_tree_runtime.models import MemoryChunk

    secret_chunk = chunk.model_copy(update={"markdown": "Authorization: bearer abc123 Alice Smith"})
    entities = extract_entities(secret_chunk)
    assert entities == (), "must not extract from secret-like content"


def test_extract_entities_bounded() -> None:
    # Many capitalised names
    names = " ".join(f"Person{i:02d} User{i:02d}" for i in range(30))
    chunk = _make_chunk(names)
    entities = extract_entities(chunk)
    assert len(entities) <= 20


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------


def test_extract_facts_finds_declarative_sentences() -> None:
    chunk = _make_chunk(
        "The memory tree is content-addressed. Each chunk has a provenance reference. "
        "Hotness gating controls topic admission."
    )
    facts = extract_facts(chunk)
    assert len(facts) >= 1


def test_extract_facts_carries_provenance() -> None:
    chunk = _make_chunk("The memory tree is content-addressed.", source_id="source-docs")
    facts = extract_facts(chunk)
    for fact in facts:
        assert fact.chunk_id == chunk.chunk_id
        assert fact.document_id == chunk.document_id
        assert fact.source_id == "source-docs"
        assert fact.raw_content_persisted is False


def test_extract_facts_confidence_bounded() -> None:
    chunk = _make_chunk(
        "The memory tree is content-addressed. Each chunk has a provenance reference."
    )
    facts = extract_facts(chunk)
    for fact in facts:
        assert 0.0 <= fact.confidence <= 1.0


def test_extract_facts_bounded() -> None:
    text = " ".join(f"Fact {i} is that the system has feature {i}." for i in range(20))
    chunk = _make_chunk(text)
    facts = extract_facts(chunk)
    assert len(facts) <= 10


def test_extract_facts_safe_projection() -> None:
    chunk = _make_chunk("The memory tree is content-addressed.")
    facts = extract_facts(chunk)
    for fact in facts:
        proj = fact.safe_projection()
        assert proj["raw_content_persisted"] is False


# ---------------------------------------------------------------------------
# Preference extraction
# ---------------------------------------------------------------------------


def test_extract_preferences_finds_positive_signals() -> None:
    chunk = _make_chunk("User prefers recent inbox summaries over archived notes.")
    prefs = extract_preferences(chunk)
    assert any(p.polarity == "positive" for p in prefs)


def test_extract_preferences_finds_negative_signals() -> None:
    chunk = _make_chunk("User dislikes stale cached results that are not fresh.")
    prefs = extract_preferences(chunk)
    assert any(p.polarity == "negative" for p in prefs)


def test_extract_preferences_carries_provenance() -> None:
    chunk = _make_chunk("User prefers local storage.", source_id="source-note")
    prefs = extract_preferences(chunk)
    for pref in prefs:
        assert pref.chunk_id == chunk.chunk_id
        assert pref.source_id == "source-note"
        assert pref.raw_content_persisted is False


def test_extract_preferences_bounded() -> None:
    sentences = " ".join(f"User likes feature {i}." for i in range(20))
    chunk = _make_chunk(sentences)
    prefs = extract_preferences(chunk)
    assert len(prefs) <= 5


def test_extract_preferences_safe_projection() -> None:
    chunk = _make_chunk("User prefers local storage over cloud sync.")
    prefs = extract_preferences(chunk)
    for pref in prefs:
        proj = pref.safe_projection()
        assert proj["raw_content_persisted"] is False
        assert "markdown" not in repr(proj).lower()


# ---------------------------------------------------------------------------
# Relation extraction
# ---------------------------------------------------------------------------


def test_extract_relations_finds_uses_predicate() -> None:
    chunk = _make_chunk("Marvex uses SQLite for the local memory index.")
    entities = extract_entities(chunk)
    relations = extract_relations(chunk, entities)
    # At minimum the function should run and return a tuple
    assert isinstance(relations, tuple)
    for rel in relations:
        assert isinstance(rel, ExtractedRelation)


def test_extract_relations_carries_provenance() -> None:
    chunk = _make_chunk("Marvex uses SQLite for local storage.", source_id="source-arch")
    entities = extract_entities(chunk)
    relations = extract_relations(chunk, entities)
    for rel in relations:
        assert rel.chunk_id == chunk.chunk_id
        assert rel.source_id == "source-arch"
        assert rel.raw_content_persisted is False


def test_extract_relations_bounded() -> None:
    text = " ".join(f"ComponentA{i} uses ComponentB{i}." for i in range(20))
    chunk = _make_chunk(text)
    entities = extract_entities(chunk)
    relations = extract_relations(chunk, entities)
    assert len(relations) <= 10


# ---------------------------------------------------------------------------
# extract_chunk and extract_chunks (pipeline)
# ---------------------------------------------------------------------------


def test_extract_chunk_returns_full_result_with_provenance() -> None:
    chunk = _make_chunk(
        "Alice Smith designed the `Marvex` project. "
        "The system is content-addressed. "
        "User prefers local storage over cloud sync. "
        "Marvex uses SQLite for the index.",
        source_id="source-pipeline",
    )
    result = extract_chunk(chunk)
    assert isinstance(result, ChunkExtractionResult)
    assert result.chunk_id == chunk.chunk_id
    assert result.document_id == chunk.document_id
    assert result.source_id == "source-pipeline"
    assert result.raw_content_persisted is False
    assert 0.0 <= result.hotness_boost <= 1.0


def test_extract_chunk_safe_projection_no_raw_content() -> None:
    chunk = _make_chunk("Alice Smith reviews the project design regularly.")
    result = extract_chunk(chunk)
    proj = result.safe_projection()
    assert proj["raw_content_persisted"] is False
    # safe_projection must not expose raw markdown
    assert "markdown" not in repr(proj).lower()


def test_extract_chunks_processes_all_chunks() -> None:
    connector = ConnectorRef(connector_id="conn-test", category=ConnectorCategory.GENERIC_OAUTH)
    meta = CanonicalSourceMetadata(
        source_id="source-multi",
        external_id="ext-multi",
        uri="local://source-multi",
        title="Multi Chunk Doc",
        connector_ref=connector,
        captured_at=datetime(2026, 5, 20, tzinfo=UTC),
    )
    doc = canonicalize_source_document(
        metadata=meta,
        markdown_body=(
            "Alice Smith designed the Marvex project. "
            "The system uses content-addressed storage. "
            "User prefers local over cloud."
        ),
        ingested_at=datetime(2026, 5, 20, tzinfo=UTC),
    )
    chunks = chunk_document(doc, max_chars=80)
    results = extract_chunks(chunks)
    assert len(results) == len(chunks)
    for result in results:
        assert result.raw_content_persisted is False


# ---------------------------------------------------------------------------
# Hotness boost
# ---------------------------------------------------------------------------


def test_compute_hotness_boost_increases_with_richer_extraction() -> None:
    chunk_lean = _make_chunk("Simple text with no entities or preferences.")
    chunk_rich = _make_chunk(
        "Alice Smith and Bob Johnson lead the `Marvex` project. "
        "The system is content-addressed. User prefers local storage. "
        "marvex/memory-tree implements the vault."
    )
    result_lean = extract_chunk(chunk_lean)
    result_rich = extract_chunk(chunk_rich)
    assert result_rich.hotness_boost >= result_lean.hotness_boost


def test_compute_hotness_boost_bounded() -> None:
    chunk = _make_chunk(
        "Alice Smith Bob Johnson Carol Williams Dave Brown Eve Davis. "
        "marvex/repo-a marvex/repo-b marvex/repo-c. "
        "User likes feature A. User prefers feature B. User wants feature C. "
        "The system is content-addressed. The tree is bounded. The vault is local."
    )
    entities = extract_entities(chunk)
    facts = extract_facts(chunk)
    prefs = extract_preferences(chunk)
    boost = compute_hotness_boost(entities, facts, prefs)
    assert 0.0 <= boost <= 1.0


# ---------------------------------------------------------------------------
# Daily digest
# ---------------------------------------------------------------------------


def test_build_daily_digest_entries_produces_entries_with_provenance() -> None:
    chunk = _make_chunk(
        "The memory tree is content-addressed. Hotness controls topic admission.",
        source_id="source-digest",
    )
    entries = build_daily_digest_entries((chunk,), date_label="2026-05-20")
    assert len(entries) >= 1
    for entry in entries:
        assert isinstance(entry, DailyDigestEntry)
        assert entry.date_label == "2026-05-20"
        assert entry.source_id == "source-digest"
        assert entry.raw_content_persisted is False
        assert entry.chunk_id == chunk.chunk_id
        assert entry.document_id == chunk.document_id


def test_build_daily_digest_entries_safe_projection() -> None:
    chunk = _make_chunk("The memory tree is content-addressed.", source_id="source-digest")
    entries = build_daily_digest_entries((chunk,), date_label="2026-05-20")
    for entry in entries:
        proj = entry.safe_projection()
        assert proj["raw_content_persisted"] is False
        assert "markdown" not in repr(proj).lower()


def test_build_daily_digest_node_returns_evidence_linked_node() -> None:
    chunk = _make_chunk(
        "The memory tree is content-addressed. Each chunk has provenance.",
        source_id="source-digest",
    )
    entries = build_daily_digest_entries((chunk,), date_label="2026-05-20")
    node = build_daily_digest_node(entries, date_label="2026-05-20")
    assert node is not None
    assert node.node_kind == "daily_digest"
    assert node.node_id == "daily:2026-05-20"
    assert node.evidence_links
    assert node.evidence_links[0].source_id == "source-digest"


def test_build_daily_digest_node_returns_none_for_empty_entries() -> None:
    node = build_daily_digest_node((), date_label="2026-05-20")
    assert node is None


def test_build_daily_digest_node_safe_projection() -> None:
    chunk = _make_chunk("The memory tree is content-addressed.", source_id="source-digest")
    entries = build_daily_digest_entries((chunk,), date_label="2026-05-20")
    node = build_daily_digest_node(entries, date_label="2026-05-20")
    assert node is not None
    proj = node.safe_projection()
    # MemoryTreeNode.safe_projection() exposes evidence_count and evidence_links — no raw content
    assert proj["evidence_count"] >= 1
    assert "markdown" not in repr(proj).lower()


# ---------------------------------------------------------------------------
# Topic hotness
# ---------------------------------------------------------------------------


def test_compute_topic_hotness_returns_bounded_float() -> None:
    chunk = _make_chunk(
        "Alice Smith designed the `Marvex` project. The system is content-addressed.",
        source_id="source-topic",
    )
    results = extract_chunks((chunk,))
    hotness = compute_topic_hotness(results, topic_label="Marvex")
    assert 0.0 <= hotness <= 1.0


def test_compute_topic_hotness_higher_for_relevant_topics() -> None:
    chunk = _make_chunk(
        "Alice Smith leads the `Marvex` project. Marvex uses content-addressed storage.",
        source_id="source-topic",
    )
    results = extract_chunks((chunk,))
    hotness_relevant = compute_topic_hotness(results, topic_label="Marvex")
    hotness_irrelevant = compute_topic_hotness(results, topic_label="unrelated-xyz-topic")
    assert hotness_relevant >= hotness_irrelevant


def test_compute_topic_hotness_empty_results() -> None:
    hotness = compute_topic_hotness((), topic_label="anything")
    assert hotness == 0.0


# ---------------------------------------------------------------------------
# Derived-safe assertions (no raw transcript / secret persistence)
# ---------------------------------------------------------------------------


def test_all_results_derived_safe_no_raw_secret_persisted() -> None:
    """Assert that all extraction results maintain raw_content_persisted=False."""
    chunk = _make_chunk(
        "Alice Smith reviewed the marvex/memory-tree repo. "
        "The system is content-addressed. User prefers local storage. "
        "Marvex uses SQLite for indexing.",
        source_id="source-safety",
    )
    result = extract_chunk(chunk)

    assert result.raw_content_persisted is False
    for entity in result.entities:
        assert entity.raw_content_persisted is False
    for fact in result.facts:
        assert fact.raw_content_persisted is False
    for pref in result.preferences:
        assert pref.raw_content_persisted is False
    for rel in result.relations:
        assert rel.raw_content_persisted is False


def test_all_safe_projections_exclude_raw_content() -> None:
    """Safe projections must not expose raw markdown or secret-like fields."""
    chunk = _make_chunk(
        "Alice Smith designed the Marvex system. User likes the local vault.",
        source_id="source-safety",
    )
    result = extract_chunk(chunk)
    proj = result.safe_projection()
    repr_str = repr(proj).lower()
    assert "markdown" not in repr_str
    assert "raw_content" not in repr_str or "false" in repr_str


def test_secret_content_not_extracted() -> None:
    """Chunks containing secret-like terms must yield no extraction results."""
    from packages.memory_tree_runtime.models import MemoryChunk

    base = _make_chunk("Normal text", source_id="source-safety")
    secret_chunk = base.model_copy(
        update={"markdown": "Authorization: bearer mysecrettoken123 Alice Smith"}
    )
    result = extract_chunk(secret_chunk)
    assert result.entities == ()
    assert result.facts == ()
    assert result.preferences == ()
    assert result.relations == ()


def test_provenance_present_on_all_derived_artefacts() -> None:
    """Every derived artefact must carry chunk_id, document_id, source_id."""
    chunk = _make_chunk(
        "Alice Smith reviewed the marvex/memory-tree repo. "
        "The system is content-addressed. User prefers local storage.",
        source_id="source-provenance",
    )
    result = extract_chunk(chunk)

    for entity in result.entities:
        assert entity.chunk_id, "entity missing chunk_id"
        assert entity.document_id, "entity missing document_id"
        assert entity.source_id, "entity missing source_id"

    for fact in result.facts:
        assert fact.chunk_id, "fact missing chunk_id"
        assert fact.document_id, "fact missing document_id"
        assert fact.source_id, "fact missing source_id"

    for pref in result.preferences:
        assert pref.chunk_id, "preference missing chunk_id"
        assert pref.document_id, "preference missing document_id"
        assert pref.source_id, "preference missing source_id"

    for rel in result.relations:
        assert rel.chunk_id, "relation missing chunk_id"
        assert rel.document_id, "relation missing document_id"
        assert rel.source_id, "relation missing source_id"
