from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts import SessionRef
from packages.memory_runtime import MemoryRecord, MemoryRef
from packages.memory_service_runtime import MemoryService, MemoryServiceConfig
from packages.memory_service_runtime.models import (
    MemoryEvidenceRef,
    MemoryRankingSignal,
    MemorySourceAttribution,
    make_evidence_id,
    make_saved_memory_episode_id,
)


class _GraphStore:
    def __init__(self) -> None:
        self.episodes = []
        self.forgotten = []

    def ingest_episode(self, episode):
        self.episodes.append(episode)

    def search(self, query: str, *, namespace: str, max_results: int):
        source = MemorySourceAttribution(
            source_id="graph.fact.project",
            source_type="synthesis",
            title="Graphiti temporal fact",
            uri="graphiti://graph.fact.project",
            captured_at=datetime.now(UTC),
            trust_level="synthesis",
        )
        return (
            MemoryEvidenceRef(
                evidence_id=make_evidence_id(source_id=source.source_id, content="User prefers Cedar as the project codename."),
                source=source,
                quote_preview="User prefers Cedar as the project codename.",
                fact="User prefers Cedar as the project codename.",
                ranking=MemoryRankingSignal(semantic_score=0.8, graph_score=1.0, recency_score=0.8, trust_score=0.8, explicit_importance=0.6),
            ),
        )

    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool:
        self.forgotten.append(ref_id)
        return False

    def inspect(self, *, namespace: str | None = None, max_records: int = 50):
        return ({"source_id": "graph.fact.project", "raw_content_persisted": False},)


class _VectorStore:
    def __init__(self) -> None:
        self.episodes = []
        self.forgotten = []

    def upsert_episode(self, episode):
        self.episodes.append(episode)

    def search(self, query: str, *, namespace: str, max_results: int):
        source = MemorySourceAttribution(
            source_id="vector.episode.project",
            source_type="chat",
            title="Past chat",
            uri="qdrant://vector.episode.project",
            captured_at=datetime.now(UTC),
            trust_level="system_observed",
        )
        return (
            MemoryEvidenceRef(
                evidence_id=make_evidence_id(source_id=source.source_id, content="Earlier chat said Cedar is the codename."),
                source=source,
                quote_preview="Earlier chat said Cedar is the codename.",
                fact="Earlier chat said Cedar is the codename.",
                ranking=MemoryRankingSignal(semantic_score=0.9, graph_score=0.2, recency_score=0.7, trust_score=0.6, explicit_importance=0.5),
            ),
        )

    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool:
        self.forgotten.append(ref_id)
        return False

    def inspect(self, *, namespace: str | None = None, max_records: int = 50):
        return ({"source_id": "vector.episode.project", "raw_content_persisted": False},)


class _Turn:
    schema_version = "1"
    trace_id = "trace-memory-service"
    turn_id = "turn-memory-service"
    user_visible_input = "Remember that Cedar is the project codename."
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-service")
    conversation_ref = None


def test_memory_service_ingests_turns_into_graph_and_vector_backends() -> None:
    graph = _GraphStore()
    vector = _VectorStore()
    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=graph, vector_store=vector)

    episodes = service.ingest_turn(turn_input=_Turn(), assistant_text="Stored that preference.")

    assert len(episodes) == 2
    assert len(graph.episodes) == 2
    assert len(vector.episodes) == 2
    assert all(episode.raw_content_persisted is False for episode in episodes)


def test_memory_service_retrieves_synthesizes_ranks_and_injects_context() -> None:
    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=_GraphStore(), vector_store=_VectorStore())

    bundle = service.retrieve_context("What project codename do I prefer?", session_ref=_Turn.session_ref)

    assert bundle.result_count == 2
    assert bundle.evidence_refs[0].citation_id.startswith("memory.evidence.")
    assert bundle.synthesis is not None
    assert "Relevant memory" in bundle.synthesis.summary
    assert "[memory.evidence." in bundle.injected_context
    assert bundle.safe_projection()["raw_context_persisted"] is False


def test_memory_service_retrieval_degrades_when_optional_graph_backend_fails() -> None:
    class FailingGraph(_GraphStore):
        def search(self, query: str, *, namespace: str, max_results: int):
            raise RuntimeError("graph offline")

    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=FailingGraph(), vector_store=_VectorStore())

    bundle = service.retrieve_context("What project codename do I prefer?", session_ref=_Turn.session_ref)

    assert bundle.result_count == 1
    assert bundle.evidence_refs[0].source.source_id == "vector.episode.project"
    assert "Earlier chat said Cedar is the codename." in bundle.injected_context


def test_memory_service_retrieval_raises_when_required_graph_backend_fails() -> None:
    class FailingGraph(_GraphStore):
        def search(self, query: str, *, namespace: str, max_results: int):
            raise RuntimeError("graph offline")

    service = MemoryService(
        config=MemoryServiceConfig(namespace="marvex", graph_required=True),
        graph_store=FailingGraph(),
        vector_store=_VectorStore(),
    )

    try:
        service.retrieve_context("What project codename do I prefer?", session_ref=_Turn.session_ref)
    except RuntimeError as exc:
        assert "graph offline" in str(exc)
    else:
        raise AssertionError("required graph retrieval failure should raise")


def test_memory_service_retrieval_degrades_when_optional_vector_backend_fails() -> None:
    class FailingVector(_VectorStore):
        def search(self, query: str, *, namespace: str, max_results: int):
            raise RuntimeError("vector offline")

    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=_GraphStore(), vector_store=FailingVector())

    bundle = service.retrieve_context("What project codename do I prefer?", session_ref=_Turn.session_ref)

    assert bundle.result_count == 1
    assert bundle.evidence_refs[0].source.source_id == "graph.fact.project"
    assert "User prefers Cedar as the project codename." in bundle.injected_context


def test_memory_service_retrieval_raises_when_required_vector_backend_fails() -> None:
    class FailingVector(_VectorStore):
        def search(self, query: str, *, namespace: str, max_results: int):
            raise RuntimeError("vector offline")

    service = MemoryService(
        config=MemoryServiceConfig(namespace="marvex", vector_required=True),
        graph_store=_GraphStore(),
        vector_store=FailingVector(),
    )

    try:
        service.retrieve_context("What project codename do I prefer?", session_ref=_Turn.session_ref)
    except RuntimeError as exc:
        assert "vector offline" in str(exc)
    else:
        raise AssertionError("required vector retrieval failure should raise")


def test_memory_service_ingests_approved_memory_record_as_saved_memory_episode() -> None:
    graph = _GraphStore()
    vector = _VectorStore()
    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=graph, vector_store=vector)

    episode = service.ingest_memory_record(
        MemoryRecord(
            schema_version="1",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory.codename"),
            scope="session",
            memory_kind="fact",
            session_ref=_Turn.session_ref,
            conversation_ref=None,
            trace_id="trace-memory-service",
            turn_id="turn-memory-service",
            content="User prefers Cedar as the project codename.",
            write_authorization="explicit_user",
            created_at=datetime.now(UTC),
            tags=("project",),
            raw_transcript_persisted=False,
        )
    )

    assert episode.kind == "saved_memory"
    assert episode.source.source_type == "saved_memory"
    assert graph.episodes[-1] == episode
    assert vector.episodes[-1] == episode


def test_memory_service_forgets_saved_memory_ref_by_durable_episode_id() -> None:
    graph = _GraphStore()
    vector = _VectorStore()
    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=graph, vector_store=vector)
    record = MemoryRecord(
        schema_version="1",
        memory_ref=MemoryRef(ref_type="memory", ref_id="memory.codename"),
        scope="session",
        memory_kind="fact",
        session_ref=_Turn.session_ref,
        conversation_ref=None,
        trace_id="trace-memory-service",
        turn_id="turn-memory-service",
        content="User prefers Cedar as the project codename.",
        write_authorization="explicit_user",
        created_at=datetime.now(UTC),
        raw_transcript_persisted=False,
    )

    episode = service.ingest_memory_record(record)
    service.forget("memory.codename")

    expected_episode_id = make_saved_memory_episode_id("memory.codename")
    assert episode.episode_id == expected_episode_id
    assert expected_episode_id in graph.forgotten
    assert expected_episode_id in vector.forgotten


def test_memory_service_health_reports_backend_readiness_without_secrets() -> None:
    class GraphWithHealth(_GraphStore):
        def health(self):
            return {
                "backend": "graphiti",
                "status": "configured",
                "llm_configured": True,
                "api_key": "must-not-leak",
                "raw_content_persisted": False,
            }

    class VectorWithHealth(_VectorStore):
        def health(self):
            return {
                "backend": "qdrant",
                "status": "configured",
                "embedding_model": "BAAI/bge-small-en-v1.5",
                "raw_content_persisted": False,
            }

    service = MemoryService(
        config=MemoryServiceConfig(namespace="marvex"),
        graph_store=GraphWithHealth(),
        vector_store=VectorWithHealth(),
    )

    health = service.health()

    assert health["schema_version"] == "1"
    assert health["status"] == "configured"
    assert health["backend_count"] == 2
    assert "must-not-leak" not in str(health)
    assert health["raw_content_persisted"] is False


def test_memory_service_close_releases_backend_resources() -> None:
    class ClosableGraph(_GraphStore):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        def close(self):
            self.closed = True

    class ClosableVector(_VectorStore):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        def close(self):
            self.closed = True

    graph = ClosableGraph()
    vector = ClosableVector()
    service = MemoryService(config=MemoryServiceConfig(namespace="marvex"), graph_store=graph, vector_store=vector)

    service.close()

    assert graph.closed is True
    assert vector.closed is True
