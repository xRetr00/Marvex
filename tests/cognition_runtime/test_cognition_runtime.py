from __future__ import annotations

from datetime import UTC, datetime

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.cognition_runtime import CognitionRuntime
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchFreshness, WebSearchGroundingBundle, WebSearchQuery, WebSearchResult


class FakeSearchProvider:
    provider_name = "fake_search"

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        result = WebSearchResult(
            title="Current release evidence",
            url="https://example.test/current-release",
            domain="example.test",
            snippet="Current release evidence summary.",
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
        trace_id="trace-cognition",
        event_id="event-cognition",
        text=text,
        timestamp=datetime(2026, 5, 21, 8, 0, tzinfo=UTC),
        session_id="session-cognition",
    )
    return build_turn_input_from_event(
        schema_version="1",
        trace_id="trace-cognition",
        turn_id="turn-cognition",
        input_event=event,
    )


def test_cognition_assembles_intent_context_prompt_and_step_plan_for_fresh_turn() -> None:
    result = CognitionRuntime(web_search_provider=FakeSearchProvider()).assemble_turn(
        _turn_input("What is the latest browser-use release? Cite sources.")
    )

    projection = result.safe_projection()

    assert projection.intent_kind == "grounded_answer"
    assert projection.grounding_required is True
    assert projection.web_search_required is True
    assert projection.evidence_ref_count == 1
    assert projection.prompt_section_count >= 3
    assert [step.step_kind for step in result.step_plan.steps] == [
        "plan",
        "web_search",
        "grounded_answer",
        "finalize",
    ]
    assert result.raw_prompt_persisted is False
    assert result.raw_context_persisted is False
    assert result.raw_payload_persisted is False
    assert "latest browser-use release" not in projection.model_dump_json().lower()


def test_cognition_uses_web_search_for_temporal_release_question_without_search_keyword() -> None:
    result = CognitionRuntime(web_search_provider=FakeSearchProvider()).assemble_turn(
        _turn_input("What model did OpenAI release this month?")
    )

    assert result.intent_projection.selected_intent["intent_kind"] == "web_search"
    assert result.web_search_required is True
    assert result.grounding_required is True
    assert result.web_search_bundle is not None
    assert result.evidence_refs[0].ref_id == "web.evidence.1"
    assert [step.step_kind for step in result.step_plan.steps] == [
        "plan",
        "web_search",
        "grounded_answer",
        "finalize",
    ]


def test_cognition_safe_tool_turn_has_tool_step_without_grounding() -> None:
    result = CognitionRuntime().assemble_turn(_turn_input("Use the calculator tool for 2+2"))

    assert result.intent_projection.selected_intent["intent_kind"] == "capability_tool"
    assert result.grounding_required is False
    assert result.web_search_required is False
    assert [step.step_kind for step in result.step_plan.steps] == ["plan", "tool", "finalize"]
    assert "capability_schema" in result.prompt_projection.section_kinds
