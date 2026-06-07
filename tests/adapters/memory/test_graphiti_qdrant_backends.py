from __future__ import annotations

from datetime import UTC, datetime


def _episode(episode_id: str = "episode.marvex.session.turn"):
    from packages.contracts import SessionRef
    from packages.memory_service_runtime.models import MemoryEpisode, MemorySourceAttribution

    return MemoryEpisode(
        episode_id=episode_id,
        namespace="marvex.session.test",
        kind="saved_memory",
        source=MemorySourceAttribution(
            source_id="saved.memory-1",
            source_type="saved_memory",
            title="memory-1",
            uri="local://memory/memory-1",
            captured_at=datetime(2026, 5, 18, tzinfo=UTC),
            trust_level="explicit_user",
        ),
        content="User prefers concise updates.",
        occurred_at=datetime(2026, 5, 18, tzinfo=UTC),
        session_ref=SessionRef(ref_type="session", ref_id="session-test"),
    )


def test_graphiti_backend_normalizes_marvex_namespaces_for_group_ids() -> None:
    from packages.adapters.memory.graphiti_backend import _graphiti_group_id

    assert _graphiti_group_id("marvex.session.session-memory-fidelity") == "marvex_session_session_memory_fidelity"
    assert _graphiti_group_id("...") == "marvex"


def test_graphiti_backend_constructs_explicit_openai_compatible_clients_without_leaking_config() -> None:
    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, GraphitiMemoryGraphStore, _cross_encoder, _embedder, _llm_client

    config = GraphitiBackendConfig(
        llm_api_key="memory-secret",
        llm_base_url="http://127.0.0.1:9999/v1",
        llm_model="local-memory-model",
        llm_small_model="local-memory-small",
        embedding_api_key="embedding-secret",
        embedding_base_url="http://127.0.0.1:9998/v1",
        embedding_model="text-embedding-3-small",
        embedding_dim=1024,
        reranker_api_key="reranker-secret",
        reranker_base_url="http://127.0.0.1:9997/v1",
        reranker_model="local-reranker",
    )

    llm = _llm_client(config)
    embedder = _embedder(config)
    reranker = _cross_encoder(config)
    store = GraphitiMemoryGraphStore(config)

    assert llm.model == "local-memory-model"
    assert llm.small_model == "local-memory-small"
    assert str(llm.client.base_url) == "http://127.0.0.1:9999/v1/"
    assert embedder.config.embedding_model == "text-embedding-3-small"
    assert str(embedder.client.base_url) == "http://127.0.0.1:9998/v1/"
    assert reranker.config.model == "local-reranker"
    assert str(reranker.client.base_url) == "http://127.0.0.1:9997/v1/"
    assert "memory-secret" not in str(store.health())


def test_graphiti_backend_can_use_openai_generic_client_for_lm_studio() -> None:
    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, _llm_client

    config = GraphitiBackendConfig(
        llm_client_kind="openai_generic",
        llm_api_key="lm-studio",
        llm_base_url="http://127.0.0.1:1234/v1",
        llm_model="google/gemma-4-e2b",
        llm_small_model="google/gemma-4-e2b",
    )

    llm = _llm_client(config)

    assert type(llm).__name__ == "OpenAIGenericClient"
    assert llm.model == "google/gemma-4-e2b"
    assert str(llm.client.base_url) == "http://127.0.0.1:1234/v1/"


def test_graphiti_backend_records_returned_episode_uuid_and_forgets_episode() -> None:
    from types import SimpleNamespace

    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, GraphitiMemoryGraphStore

    class FakeGraphiti:
        def __init__(self) -> None:
            self.added = []
            self.removed = []

        async def add_episode(self, **kwargs):
            self.added.append(kwargs)
            return SimpleNamespace(episode=SimpleNamespace(uuid="11111111-1111-4111-8111-111111111111"))

        async def remove_episode(self, episode_uuid: str):
            self.removed.append(episode_uuid)

    graphiti = FakeGraphiti()
    episode = _episode()
    store = GraphitiMemoryGraphStore(GraphitiBackendConfig(), graphiti=graphiti)

    store.ingest_episode(episode)
    forgotten = store.forget(episode.episode_id)

    assert "uuid" not in graphiti.added[0]
    assert forgotten is True
    assert graphiti.removed == ["11111111-1111-4111-8111-111111111111"]


def test_graphiti_backend_forget_accepts_raw_graphiti_episode_uuid() -> None:
    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, GraphitiMemoryGraphStore

    class FakeGraphiti:
        def __init__(self) -> None:
            self.removed = []

        async def remove_episode(self, episode_uuid: str):
            self.removed.append(episode_uuid)

    graphiti = FakeGraphiti()
    raw_uuid = "22222222-2222-4222-8222-222222222222"
    store = GraphitiMemoryGraphStore(GraphitiBackendConfig(), graphiti=graphiti)

    forgotten = store.forget(raw_uuid)

    assert forgotten is True
    assert graphiti.removed == [raw_uuid]


def test_graphiti_backend_close_releases_client_and_runner() -> None:
    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, GraphitiMemoryGraphStore

    class FakeGraphiti:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    graphiti = FakeGraphiti()
    store = GraphitiMemoryGraphStore(GraphitiBackendConfig(), graphiti=graphiti)

    store.close()
    store.close()

    assert graphiti.closed is True


def test_graphiti_backend_search_uses_installed_group_ids_signature() -> None:
    from types import SimpleNamespace

    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, GraphitiMemoryGraphStore

    class FakeGraphiti:
        def __init__(self) -> None:
            self.calls = []

        async def search(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return [
                SimpleNamespace(
                    fact="User prefers Maple as the codename.",
                    uuid="edge-1",
                    created_at=datetime(2026, 5, 18, tzinfo=UTC),
                )
            ]

    graphiti = FakeGraphiti()
    store = GraphitiMemoryGraphStore(GraphitiBackendConfig(), graphiti=graphiti)

    refs = store.search("codename", namespace="marvex.session.session-1", max_results=3)

    assert len(refs) == 1
    assert graphiti.calls[0][1]["group_ids"] == ["marvex_session_session_1"]
    assert graphiti.calls[0][1]["num_results"] == 3


def test_graphiti_backend_inspects_recent_episodes_without_raw_content() -> None:
    from types import SimpleNamespace

    from packages.adapters.memory.graphiti_backend import GraphitiBackendConfig, GraphitiMemoryGraphStore

    episode = _episode("episode.saved_memory.memory-1")
    graphiti_uuid = "33333333-3333-4333-8333-333333333333"

    class FakeGraphiti:
        async def retrieve_episodes(self, *, reference_time, last_n, group_ids):
            return [
                SimpleNamespace(
                    uuid=graphiti_uuid,
                    name=episode.episode_id,
                    group_id=group_ids[0],
                    source_description="saved_memory:saved_memory:saved.memory-1",
                    source=SimpleNamespace(value="text"),
                    valid_at=datetime(2026, 5, 18, tzinfo=UTC),
                    content="raw content must not leak",
                )
            ]

    store = GraphitiMemoryGraphStore(GraphitiBackendConfig(), graphiti=FakeGraphiti())

    rows = store.inspect(namespace=episode.namespace, max_records=5)

    assert rows[0]["episode_id"] == episode.episode_id
    assert rows[0]["graphiti_episode_uuid"] == graphiti_uuid
    assert rows[0]["source_id"] == "saved.memory-1"
    assert rows[0]["raw_content_persisted"] is False
    assert "raw content must not leak" not in str(rows)


def test_qdrant_backend_uses_deterministic_uuid_point_ids() -> None:
    from uuid import UUID

    from packages.adapters.memory.qdrant_backend import _point_id

    assert UUID(_point_id("episode.marvex.session.turn")) == UUID(_point_id("episode.marvex.session.turn"))


def test_qdrant_backend_inspects_persisted_payloads_without_process_cache() -> None:
    from types import SimpleNamespace

    from packages.adapters.memory.qdrant_backend import QdrantMemoryBackendConfig, QdrantMemoryVectorStore

    class FakeQdrantClient:
        def scroll(self, **kwargs):
            assert kwargs["collection_name"] == "memory"
            assert kwargs["limit"] == 5
            return (
                [
                    SimpleNamespace(
                        payload={
                            "episode_id": "episode.saved_memory.memory-1",
                            "namespace": "marvex.session.test",
                            "kind": "saved_memory",
                            "source_id": "saved.memory-1",
                            "source_type": "saved_memory",
                            "title": "memory-1",
                            "document": "User prefers concise updates.",
                        }
                    )
                ],
                None,
            )

    store = QdrantMemoryVectorStore(QdrantMemoryBackendConfig(collection_name="memory"), client=FakeQdrantClient())

    rows = store.inspect(namespace="marvex.session.test", max_records=5)

    assert rows[0]["episode_id"] == "episode.saved_memory.memory-1"
    assert rows[0]["source_id"] == "saved.memory-1"
    assert rows[0]["content_preview"] == "User prefers concise updates."
    assert rows[0]["raw_content_persisted"] is False


def test_qdrant_backend_close_releases_client() -> None:
    from packages.adapters.memory.qdrant_backend import QdrantMemoryBackendConfig, QdrantMemoryVectorStore

    class FakeQdrantClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    client = FakeQdrantClient()
    store = QdrantMemoryVectorStore(QdrantMemoryBackendConfig(), client=client)

    store.close()

    assert client.closed is True
