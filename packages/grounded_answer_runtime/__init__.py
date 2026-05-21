
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.context_runtime import ContextCandidate, ContextSourceKind, ContextSourceRef, ContextSourceTrustLevel
from packages.intent_runtime import IntentKind
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchGroundingBundle
from packages.memory_tree_runtime.models import EvidenceLink


class GroundedAnswerDraft(CapabilityRuntimeModel):
    text: str = Field(..., min_length=1, max_length=4000)
    citation_ids: tuple[str, ...]
    raw_answer_persisted: Literal[False] = False


class CitationValidationResult(CapabilityRuntimeModel):
    valid: bool
    reason_code: str
    citation_count: int
    missing_citation_ids: tuple[str, ...] = ()
    raw_evidence_persisted: Literal[False] = False


def validate_grounded_citations(
    draft: GroundedAnswerDraft,
    *,
    evidence_refs: tuple[WebSearchEvidenceRef, ...],
    memory_evidence_refs: tuple[EvidenceLink, ...] = (),
    citations_required: bool = False,
) -> CitationValidationResult:
    allowed = {ref.evidence_id for ref in evidence_refs} | {_memory_citation_id(ref) for ref in memory_evidence_refs}
    if citations_required and not draft.citation_ids:
        return CitationValidationResult(valid=False, reason_code="citation.required_missing", citation_count=0)
    if not evidence_refs and not memory_evidence_refs:
        return CitationValidationResult(valid=False, reason_code="citation.evidence_missing", citation_count=0)
    missing = tuple(citation for citation in draft.citation_ids if citation not in allowed)
    if missing:
        return CitationValidationResult(valid=False, reason_code="citation.evidence_ref_missing", citation_count=len(draft.citation_ids), missing_citation_ids=missing)
    bracketed = tuple(re.findall(r"\[((?:web|memory)\.evidence\.[A-Za-z0-9_.:-]+)\]", draft.text))
    hallucinated = tuple(citation for citation in bracketed if citation not in allowed)
    if hallucinated:
        return CitationValidationResult(valid=False, reason_code="citation.evidence_ref_missing", citation_count=len(draft.citation_ids), missing_citation_ids=hallucinated)
    return CitationValidationResult(valid=True, reason_code="citation.validated", citation_count=len(draft.citation_ids))


def web_search_bundle_to_context_candidate(bundle: WebSearchGroundingBundle) -> ContextCandidate:
    identifier = "web.bundle." + _slug(bundle.query.query)
    lines = []
    for ref in bundle.evidence_refs[:5]:
        lines.append(f"[{ref.evidence_id}] {ref.title} - {ref.source_url} - {ref.snippet}")
    safe_summary = _bounded_text("\n".join(lines) or "No web evidence available.", 1200)
    return ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=ContextSourceKind.WEB_SEARCH_EVIDENCE, identifier=identifier),
        safe_summary,
        token_estimate=max(1, len(safe_summary.split())),
        intent_tags=(IntentKind.GROUNDED_ANSWER.value, IntentKind.WEB_SEARCH.value),
        trust_level=ContextSourceTrustLevel.UNTRUSTED_SUMMARY,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "query"


def _bounded_text(value: str, limit: int) -> str:
    return value[:limit]


def _memory_citation_id(ref: EvidenceLink) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", ref.chunk_id).strip("-")
    return f"memory.evidence.{safe}"
