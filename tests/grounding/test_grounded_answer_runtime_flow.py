from datetime import UTC, datetime

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.assistant_turn_integration import EndToEndTurnStateStore, run_end_to_end_assistant_turn
from packages.connector_runtime import ConnectorCategory, ConnectorRef
from packages.memory_tree_runtime import CanonicalSourceMetadata, MemoryTreeRuntime, canonicalize_source_document, chunk_document
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchFreshness, WebSearchGroundingBundle, WebSearchQuery, WebSearchResult


class FakeSearchProvider:
    provider_name = "fake_search"

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        result = WebSearchResult(
            title="Current browser-use release",
            url="https://example.test/browser-use-release",
            domain="example.test",
            snippet="browser-use current version evidence",
            freshness=query.freshness,
        )
        evidence = WebSearchEvidenceRef(
            evidence_id="web.evidence.1",
            source_url=result.url,
            domain=result.domain,
            title=result.title,
            snippet=result.snippet,
            freshness=query.freshness,
        )
        return WebSearchGroundingBundle(query=query, provider=self.provider_name, results=(result,), evidence_refs=(evidence,))


def _turn_input(text: str):
    event = build_text_input_event(
        schema_version="1",
        trace_id="trace-grounded-flow",
        event_id="event-grounded-flow",
        text=text,
        timestamp="2026-05-19T08:00:00+00:00",
        session_id="session-grounded-flow",
    )
    return build_turn_input_from_event(schema_version="1", trace_id="trace-grounded-flow", turn_id="turn-grounded-flow", input_event=event)


def _memory_tree() -> MemoryTreeRuntime:
    metadata = CanonicalSourceMetadata(
        source_id="source-grounded-memory",
        external_id="doc-grounded-1",
        uri="local://memory/grounded-1",
        title="Grounded Memory",
        connector_ref=ConnectorRef(connector_id="mock-memory", category=ConnectorCategory.GENERIC_OAUTH),
        captured_at=datetime(2026, 5, 19, tzinfo=UTC),
    )
    document = canonicalize_source_document(
        metadata=metadata,
        markdown_body="Memory evidence says Marvex should combine source grounded web and memory context.",
        ingested_at=datetime(2026, 5, 19, tzinfo=UTC),
    )
    return MemoryTreeRuntime.with_documents(documents=(document,), chunks=chunk_document(document, max_chars=160))


def test_grounded_answer_route_searches_and_combines_web_and_memory_evidence() -> None:
    store = EndToEndTurnStateStore()

    result = run_end_to_end_assistant_turn(
        _turn_input("Give a grounded answer with current web evidence and memory evidence about browser-use"),
        model="fake-model",
        state_store=store,
        web_search_provider=FakeSearchProvider(),
        memory_tree_runtime=_memory_tree(),
    )

    assert result.intent_projection.selected_intent["intent_kind"] == "grounded_answer"
    assert {source["kind"] for source in result.context_projection.included_sources} >= {"web_search_evidence", "memory_projection"}
    assert "evidence_context" in result.prompt_projection.section_kinds
    assert "memory_context" in result.prompt_projection.section_kinds
    assert result.prompt_projection.budget_report["within_budget"] is True
    assert result.tool_state_projection["web_evidence_count"] == 1
    assert result.tool_state_projection["citation_validation"] == "citation.validated"
    assert result.assistant_result.assistant_final_response is not None
    assert "[web.evidence.1]" in result.assistant_result.assistant_final_response.text
    serialized = result.model_dump_json().lower()
    assert "source grounded web and memory context" not in serialized
    assert "raw_payload\":true" not in serialized


def test_grounded_answer_reports_missing_evidence_when_search_unavailable() -> None:
    result = run_end_to_end_assistant_turn(
        _turn_input("Give a grounded answer about the latest browser-use release"),
        model="fake-model",
        web_search_provider=None,
    )

    assert result.intent_projection.selected_intent["intent_kind"] == "grounded_answer"
    assert result.tool_state_projection["result_status"] == "evidence_missing"
    assert result.tool_state_projection["citation_validation"] == "citation.evidence_missing"
    assert result.assistant_result.assistant_final_response is not None
    assert "Evidence is missing" in result.assistant_result.assistant_final_response.text
