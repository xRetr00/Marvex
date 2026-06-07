from __future__ import annotations


def test_core_memory_backend_config_selects_graphiti_qdrant_service(tmp_path) -> None:
    from services.core.main import CoreServiceEntrypointConfig, _memory_service_from_config
    from packages.memory_service_runtime import MemoryService

    config = CoreServiceEntrypointConfig(
        memory_backend="graphiti_qdrant",
        memory_vault_root=str(tmp_path / "memory"),
        memory_namespace="marvex-test",
        falkordb_host="localhost",
        falkordb_port=6379,
        qdrant_collection="marvex_test_memory",
        qdrant_path=str(tmp_path / "qdrant"),
        memory_llm_api_key="memory-secret",
        memory_llm_base_url="http://127.0.0.1:9999/v1",
        memory_llm_model="local-memory-model",
        memory_llm_small_model="local-memory-small",
        memory_llm_client_kind="openai_generic",
        memory_embedding_api_key="embedding-secret",
        memory_embedding_base_url="http://127.0.0.1:9998/v1",
        graphiti_embedding_model="text-embedding-3-small",
        graphiti_embedding_dim=1024,
        memory_reranker_api_key="reranker-secret",
        memory_reranker_base_url="http://127.0.0.1:9997/v1",
        memory_reranker_model="local-reranker",
    )

    service = _memory_service_from_config(config)

    try:
        assert isinstance(service, MemoryService)
        assert service.compatibility_store is not None
        health = service.health()
        assert health["backend_count"] == 3
        assert "memory-secret" not in str(health)
        graph_config = service._graph_store._config  # type: ignore[attr-defined]  # adapter config is the construction evidence.
        assert graph_config.llm_base_url == "http://127.0.0.1:9999/v1"
        assert graph_config.llm_model == "local-memory-model"
        assert graph_config.llm_client_kind == "openai_generic"
        assert graph_config.embedding_api_key == "embedding-secret"
        assert graph_config.embedding_base_url == "http://127.0.0.1:9998/v1"
        assert graph_config.reranker_model == "local-reranker"
    finally:
        if service is not None:
            service.close()


def test_core_memory_backend_config_keeps_local_backend_on_legacy_loop(tmp_path) -> None:
    from services.core.main import CoreServiceEntrypointConfig, _memory_loop_from_config, _memory_service_from_config

    config = CoreServiceEntrypointConfig(
        memory_backend="local",
        memory_vault_root=str(tmp_path / "memory"),
    )

    assert _memory_service_from_config(config) is None
    assert _memory_loop_from_config(config) is not None
