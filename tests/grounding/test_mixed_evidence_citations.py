from __future__ import annotations

from packages.grounded_answer_runtime import GroundedAnswerDraft, validate_grounded_citations
from packages.memory_tree_runtime.models import EvidenceLink
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchFreshness


def test_mixed_web_and_memory_citations_must_map_to_evidence_refs() -> None:
    web = WebSearchEvidenceRef(evidence_id="web.evidence.1", source_url="https://example.test", domain="example.test", title="Web", snippet="safe", freshness=WebSearchFreshness.CURRENT)
    memory = EvidenceLink(document_id="doc.1", chunk_id="chunk:memory:1", source_id="source.1", quote_preview="safe memory")
    draft = GroundedAnswerDraft(text="Web says current [web.evidence.1]; memory says prior [memory.evidence.chunk-memory-1].", citation_ids=("web.evidence.1", "memory.evidence.chunk-memory-1"))

    result = validate_grounded_citations(draft, evidence_refs=(web,), memory_evidence_refs=(memory,))

    assert result.valid is True
    assert result.citation_count == 2


def test_required_citations_missing_fails_even_when_evidence_exists() -> None:
    web = WebSearchEvidenceRef(evidence_id="web.evidence.1", source_url="https://example.test", domain="example.test", title="Web", snippet="safe", freshness=WebSearchFreshness.CURRENT)
    draft = GroundedAnswerDraft(text="Answer with no marker", citation_ids=())

    result = validate_grounded_citations(draft, evidence_refs=(web,), citations_required=True)

    assert result.valid is False
    assert result.reason_code == "citation.required_missing"
