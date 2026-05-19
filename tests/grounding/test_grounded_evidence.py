
from __future__ import annotations

import pytest

from packages.context_runtime import ContextBudget, ContextDeliveryPolicy, build_context_pack
from packages.grounded_answer_runtime import GroundedAnswerDraft, validate_grounded_citations, web_search_bundle_to_context_candidate
from packages.intent_runtime import IntentKind, IntentRef
from packages.prompt_harness_runtime import PromptAssemblyRequest, PromptSectionKind, assemble_prompt_harness
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchFreshness, WebSearchGroundingBundle, WebSearchQuery, WebSearchResult


def _bundle() -> WebSearchGroundingBundle:
    query = WebSearchQuery(query="latest browser-use version", freshness=WebSearchFreshness.CURRENT)
    result = WebSearchResult(title="Browser-use release", url="https://example.test/release", domain="example.test", snippet="Version evidence snippet", freshness=WebSearchFreshness.CURRENT)
    evidence = WebSearchEvidenceRef(evidence_id="web.evidence.1", source_url=result.url, domain=result.domain, title=result.title, snippet=result.snippet, freshness=WebSearchFreshness.CURRENT)
    return WebSearchGroundingBundle(query=query, provider="searxng", results=(result,), evidence_refs=(evidence,))


def test_web_search_evidence_injects_safe_prompt_section() -> None:
    candidate = web_search_bundle_to_context_candidate(_bundle())
    intent_ref = IntentRef(intent_id="intent.grounded_answer", intent_kind=IntentKind.GROUNDED_ANSWER)
    context = build_context_pack(
        schema_version="1",
        trace_id="trace-grounded",
        turn_id="turn-grounded",
        intent_ref=intent_ref,
        candidates=(candidate,),
        budget=ContextBudget(max_context_tokens=80, reserved_response_tokens=20),
        policy=ContextDeliveryPolicy(max_candidates=2),
    )

    prompt = assemble_prompt_harness(PromptAssemblyRequest(schema_version="1", trace_id="trace-grounded", turn_id="turn-grounded", intent_ref=intent_ref, context_pack=context))

    assert PromptSectionKind.EVIDENCE_CONTEXT.value in prompt.safe_projection().section_kinds
    assert prompt.plan.sections[1].source_ref.identifier == "web.bundle.latest-browser-use-version"
    assert "https://example.test/release" in prompt.plan.sections[1].safe_content
    assert "Version evidence snippet" in prompt.plan.sections[1].safe_content
    assert prompt.raw_prompt_persisted is False


def test_grounded_citation_validation_rejects_hallucinated_citations() -> None:
    bundle = _bundle()
    valid = GroundedAnswerDraft(text="The source says it is current [web.evidence.1].", citation_ids=("web.evidence.1",))
    invalid = GroundedAnswerDraft(text="Unsupported citation [web.evidence.404].", citation_ids=("web.evidence.404",))

    assert validate_grounded_citations(valid, evidence_refs=bundle.evidence_refs).valid is True
    rejected = validate_grounded_citations(invalid, evidence_refs=bundle.evidence_refs)
    assert rejected.valid is False
    assert rejected.reason_code == "citation.evidence_ref_missing"


def test_grounded_answer_requires_evidence_when_citations_are_missing() -> None:
    draft = GroundedAnswerDraft(text="Current facts need evidence.", citation_ids=())

    result = validate_grounded_citations(draft, evidence_refs=())

    assert result.valid is False
    assert result.reason_code == "citation.evidence_missing"
