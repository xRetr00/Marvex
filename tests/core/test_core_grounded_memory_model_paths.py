from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from packages.assistant_runtime.input_normalization import build_text_input_event, build_turn_input_from_event
from packages.contracts import (
    FinishReason,
    ProviderRequest,
    ProviderResponse,
)
from packages.memory_runtime import MemoryRecord, MemoryRef, SQLiteMemoryStore
from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchFreshness, WebSearchGroundingBundle, WebSearchQuery, WebSearchResult
from services.core.main import _CoreServiceProviderWorkerTurnExecutor


class RecordingProvider:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="recording",
            response_id=f"{request.turn_id}:recording-response",
            output_text=self.response_text,
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )


class FixedIntentClassifier:
    def __init__(self, intent_kind: str) -> None:
        self.intent_kind = intent_kind

    def classify(self, turn_input):
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {"intent_id": f"intent.{self.intent_kind}", "intent_kind": self.intent_kind},
                "confidence_bucket": "high",
                "risk_signal": "none",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


def _lightweight_intent_planner():
    from packages.intent_runtime.hybrid import DeterministicLocalIntentEncoder, HybridIntentRuntime

    return HybridIntentRuntime(semantic_encoder=DeterministicLocalIntentEncoder())


class RealSearchProvider:
    provider_name = "real_fixture_search"

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        result = WebSearchResult(
            title="Cedar project evidence",
            url="https://docs.marvex.local/cedar",
            domain="docs.marvex.local",
            snippet="Evidence says Cedar is the preferred codename.",
            freshness=query.freshness,
        )
        evidence = WebSearchEvidenceRef(
            evidence_id="web.evidence.1",
            source_url=result.url,
            domain=result.domain,
            title=result.title,
            snippet=result.snippet,
            freshness=WebSearchFreshness.CURRENT,
        )
        return WebSearchGroundingBundle(query=query, provider=self.provider_name, results=(result,), evidence_refs=(evidence,))


@dataclass
class _MemoryEvidence:
    document_id: str = "memory-doc"
    chunk_id: str = "memory:cedar"
    source_id: str = "memory-source"
    quote_preview: str = "Approved memory says Cedar is the preferred codename."


class MemoryTreeRuntime:
    def memory_query_with_evidence(self, _query: str):
        node = type("Node", (), {"evidence_links": (_MemoryEvidence(),)})()
        return type("Search", (), {"results": (node,)})()


def _turn_input(text: str, *, session_id: str | None = None):
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-grounded-model",
        event_id="event-core-grounded-model",
        text=text,
        timestamp="2026-05-21T08:00:00+00:00",
        session_id=session_id,
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-grounded-model",
        turn_id="turn-core-grounded-model",
        input_event=event,
    )


def _executor(provider: RecordingProvider, *, intent_kind: str, web_search_provider=None, memory_tree_runtime=None, memory_loop=None):
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=type("Trace", (), {"emit": lambda self, event: None, "read_trace": lambda self, trace_id: {"event_count": 0}})(),
        web_search_provider=web_search_provider,
        memory_tree_runtime=memory_tree_runtime,
        memory_loop=memory_loop,
        intent_planner=_lightweight_intent_planner(),
    )
    executor._provider = provider
    executor._intent_classifier = FixedIntentClassifier(intent_kind)
    return executor


def test_grounded_route_invokes_provider_with_real_evidence_and_validates_citations() -> None:
    provider = RecordingProvider("The preferred codename is Cedar [web.evidence.1].")
    result = _executor(provider, intent_kind="grounded_answer", web_search_provider=RealSearchProvider()).submit_turn(
        _turn_input("Using the evidence, what project codename do I prefer?")
    )

    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "The preferred codename is Cedar [web.evidence.1]."
    assert result.metadata["provider_boundary"] == "provider_worker_process"
    assert result.metadata["grounding"]["citation_validation"] == "citation.validated"
    assert len(provider.requests) == 1
    assert "Using the evidence" in provider.requests[0].input_text
    assert "Evidence says Cedar is the preferred codename." in provider.requests[0].input_text


def test_grounded_route_without_evidence_returns_deterministic_missing_evidence_response() -> None:
    provider = RecordingProvider("I need actual evidence before I can cite this.")
    result = _executor(provider, intent_kind="grounded_answer", web_search_provider=None).submit_turn(
        _turn_input("Give a grounded answer about a missing source.")
    )

    assert result.assistant_final_response is not None
    assert "Evidence is missing" in result.assistant_final_response.text
    assert len(provider.requests) == 0
    assert result.metadata["grounding"]["citation_validation"] == "citation.evidence_missing"
    assert result.metadata["grounding"]["evidence_ref_count"] == 0


def test_memory_route_invokes_provider_with_recalled_memory(tmp_path: Path) -> None:
    from packages.contracts import ConversationRef, SessionRef
    from packages.cognition_runtime import LocalMemoryLoop

    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    loop = LocalMemoryLoop.open(vault_root=vault_root)
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-model")
    loop.memory_store.write_record(
        MemoryRecord(
            schema_version="0.1.1-draft",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory-cedar"),
            scope="session",
            memory_kind="fact",
            session_ref=session_ref,
            conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-memory-model"),
            trace_id="trace-seed-memory",
            turn_id="turn-seed-memory",
            content="User preferred project codename is Cedar.",
            write_authorization="policy_approved",
            created_at=datetime(2026, 5, 21, 8, 0, tzinfo=UTC),
            tags=("profile",),
            raw_transcript_persisted=False,
        )
    )
    provider = RecordingProvider("Your preferred codename is Cedar.")

    result = _executor(provider, intent_kind="memory", memory_loop=loop).submit_turn(
        _turn_input("What project codename do I prefer from memory?", session_id=session_ref.ref_id)
    )

    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Your preferred codename is Cedar."
    assert len(provider.requests) == 1
    assert "User preferred project codename is Cedar." in provider.requests[0].input_text


def test_non_test_code_does_not_contain_fake_grounded_answer_templates() -> None:
    root = Path(__file__).resolve().parents[2]
    forbidden = (
        "Grounded answer from available evidence",
        "Grounded answer uses available evidence",
        "https://example.test/browser-use-release",
    )
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", ".venv/", ".git/", ".claude/", ".worktrees/")):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            if token in text:
                offenders.append(f"{rel}: {token}")

    assert offenders == []
