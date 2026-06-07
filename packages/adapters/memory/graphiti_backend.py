"""Graphiti-backed memory graph adapter.

This adapter keeps Graphiti isolated behind Marvex memory-service contracts.
It supports FalkorDB as the local/self-hosted default and can also be pointed
at Neo4j by constructing the Graphiti client accordingly.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import threading
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from packages.memory_service_runtime.models import (
    MemoryEpisode,
    MemoryEvidenceRef,
    MemoryRankingSignal,
    MemorySourceAttribution,
    bounded_preview,
    make_evidence_id,
)


class GraphitiBackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GraphitiBackendConfig:
    backend: str = "falkordb"
    namespace: str = "marvex"
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_small_model: str | None = None
    llm_client_kind: str = "openai_responses"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1024
    reranker_api_key: str | None = None
    reranker_base_url: str | None = None
    reranker_model: str | None = None
    build_indices_on_start: bool = True


class GraphitiMemoryGraphStore:
    def __init__(self, config: GraphitiBackendConfig, *, graphiti: Any | None = None) -> None:
        self._config = config
        self._graphiti = graphiti
        self._initialized = graphiti is not None
        self._runner = _AsyncRunner()
        self._episode_uuid_by_id: dict[str, str] = {}

    def ingest_episode(self, episode: MemoryEpisode) -> None:
        graphiti = self._client()
        episode_type = _episode_type(episode.kind)
        result = self._runner.run(
            graphiti.add_episode(
                name=episode.episode_id,
                episode_body=episode.content,
                source=episode_type,
                source_description=f"{episode.kind}:{episode.source.source_type}:{episode.source.source_id}",
                reference_time=episode.occurred_at,
                group_id=_graphiti_group_id(episode.namespace),
            )
        )
        graphiti_episode_uuid = str(getattr(getattr(result, "episode", None), "uuid", "") or "")
        if graphiti_episode_uuid:
            self._episode_uuid_by_id[episode.episode_id] = graphiti_episode_uuid

    def search(self, query: str, *, namespace: str, max_results: int) -> tuple[MemoryEvidenceRef, ...]:
        graphiti = self._client()
        raw_results = self._runner.run(
            graphiti.search(
                query,
                group_ids=[_graphiti_group_id(namespace)],
                num_results=max_results,
            )
        )
        refs: list[MemoryEvidenceRef] = []
        for rank, item in enumerate(tuple(raw_results)[:max_results]):
            fact = str(getattr(item, "fact", "") or getattr(item, "name", "") or item)
            if not fact.strip():
                continue
            source_id = str(getattr(item, "uuid", "") or getattr(item, "source_node_uuid", "") or f"graphiti.{rank}")
            source = MemorySourceAttribution(
                source_id=f"graphiti.{source_id}",
                source_type="synthesis",
                title="Graphiti temporal fact",
                uri=f"graphiti://{source_id}",
                captured_at=getattr(item, "created_at", None) or getattr(item, "valid_at", None) or _utc_now(),
                trust_level="synthesis",
            )
            score = max(0.0, 1.0 - (rank * 0.08))
            refs.append(
                MemoryEvidenceRef(
                    evidence_id=make_evidence_id(source_id=source.source_id, content=fact),
                    source=source,
                    quote_preview=bounded_preview(fact),
                    episode_id=str(getattr(item, "episode_uuid", "") or "") or None,
                    fact=bounded_preview(fact, limit=500),
                    valid_at=getattr(item, "valid_at", None),
                    invalid_at=getattr(item, "invalid_at", None),
                    ranking=MemoryRankingSignal(
                        semantic_score=score,
                        graph_score=score,
                        recency_score=0.7,
                        trust_score=0.75,
                        explicit_importance=0.5,
                    ),
                )
            )
        return tuple(refs)

    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool:
        graphiti = self._client()
        graphiti_uuid = _graphiti_forget_uuid(ref_id) or self._episode_uuid_by_id.get(ref_id)
        if not graphiti_uuid:
            graphiti_uuid = self._lookup_episode_uuid(ref_id, namespace=namespace)
        if not graphiti_uuid:
            return False
        try:
            self._runner.run(graphiti.remove_episode(graphiti_uuid))
            self._episode_uuid_by_id.pop(ref_id, None)
            return True
        except Exception:
            return False

    def inspect(self, *, namespace: str | None = None, max_records: int = 50) -> tuple[dict[str, object], ...]:
        target_namespace = namespace or self._config.namespace
        try:
            episodes = self._runner.run(
                self._client().retrieve_episodes(
                    reference_time=_utc_now(),
                    last_n=max_records,
                    group_ids=[_graphiti_group_id(target_namespace)],
                )
            )
        except Exception:
            return (
                {
                    "backend": "graphiti",
                    "backend_kind": self._config.backend,
                    "namespace": target_namespace,
                    "status": "unavailable",
                    "raw_content_persisted": False,
                },
            )
        rows: list[dict[str, object]] = []
        for episode in tuple(episodes)[:max_records]:
            source = _source_from_description(str(getattr(episode, "source_description", "") or ""))
            rows.append(
                {
                    "backend": "graphiti",
                    "backend_kind": self._config.backend,
                    "namespace": target_namespace,
                    "status": "configured",
                    "episode_id": str(getattr(episode, "name", "") or getattr(episode, "uuid", "")),
                    "graphiti_episode_uuid": str(getattr(episode, "uuid", "")),
                    "source_id": source.get("source_id", ""),
                    "source_type": source.get("source_type", ""),
                    "kind": source.get("kind", ""),
                    "valid_at": getattr(episode, "valid_at", None).isoformat() if getattr(episode, "valid_at", None) is not None else None,
                    "raw_content_persisted": False,
                }
            )
        return tuple(rows)

    def health(self) -> dict[str, object]:
        return {
            "backend": "graphiti",
            "backend_kind": self._config.backend,
            "status": "configured",
            "namespace": self._config.namespace,
            "graphiti_dependency_available": importlib.util.find_spec("graphiti_core") is not None,
            "falkordb_dependency_available": importlib.util.find_spec("graphiti_core.driver.falkordb_driver") is not None if self._config.backend == "falkordb" else None,
            "llm_configured": bool(self._config.llm_api_key or self._config.llm_base_url),
            "llm_client_kind": self._config.llm_client_kind,
            "llm_base_url_configured": bool(self._config.llm_base_url),
            "llm_model": self._config.llm_model,
            "llm_small_model": self._config.llm_small_model,
            "embedding_configured": bool(self._config.embedding_api_key or self._config.embedding_base_url),
            "embedding_base_url_configured": bool(self._config.embedding_base_url),
            "embedding_model": self._config.embedding_model,
            "embedding_dim": self._config.embedding_dim,
            "reranker_configured": bool(self._config.reranker_api_key or self._config.reranker_base_url or self._config.reranker_model),
            "reranker_base_url_configured": bool(self._config.reranker_base_url),
            "reranker_model": self._config.reranker_model,
            "build_indices_on_start": self._config.build_indices_on_start,
            "raw_content_persisted": False,
        }

    def close(self) -> None:
        graphiti = self._graphiti
        if graphiti is not None and hasattr(graphiti, "close"):
            result = graphiti.close()
            if inspect.isawaitable(result):
                self._runner.run(result)
        self._graphiti = None
        self._initialized = False
        self._episode_uuid_by_id.clear()
        self._runner.close()

    def _client(self) -> Any:
        if self._graphiti is None:
            self._graphiti = self._build_client()
        if not self._initialized and self._config.build_indices_on_start:
            self._runner.run(self._graphiti.build_indices_and_constraints())
            self._initialized = True
        return self._graphiti

    def _build_client(self) -> Any:
        try:
            from graphiti_core import Graphiti
        except Exception as exc:  # noqa: BLE001
            raise GraphitiBackendUnavailable("graphiti-core is not installed") from exc

        if self._config.backend == "falkordb":
            try:
                from graphiti_core.driver.falkordb_driver import FalkorDriver
            except Exception as exc:  # noqa: BLE001
                raise GraphitiBackendUnavailable("graphiti-core[falkordb] is not installed") from exc
            driver = FalkorDriver(
                host=self._config.falkordb_host,
                port=str(self._config.falkordb_port),
                username=self._config.falkordb_username,
                password=self._config.falkordb_password,
            )
            return Graphiti(
                graph_driver=driver,
                llm_client=_llm_client(self._config),
                embedder=_embedder(self._config),
                cross_encoder=_cross_encoder(self._config),
                store_raw_episode_content=False,
            )
        return Graphiti(
            self._config.neo4j_uri,
            self._config.neo4j_user,
            self._config.neo4j_password,
            llm_client=_llm_client(self._config),
            embedder=_embedder(self._config),
            cross_encoder=_cross_encoder(self._config),
            store_raw_episode_content=False,
        )

    def _lookup_episode_uuid(self, ref_id: str, *, namespace: str | None) -> str | None:
        if namespace is None:
            return None
        try:
            episodes = self._runner.run(
                self._client().retrieve_episodes(
                    reference_time=_utc_now(),
                    last_n=100,
                    group_ids=[_graphiti_group_id(namespace)],
                )
            )
        except Exception:
            return None
        for episode in episodes:
            if str(getattr(episode, "name", "") or "") == ref_id:
                graphiti_uuid = str(getattr(episode, "uuid", "") or "")
                if graphiti_uuid:
                    self._episode_uuid_by_id[ref_id] = graphiti_uuid
                    return graphiti_uuid
        return None


def _episode_type(kind: str) -> Any:
    try:
        from graphiti_core.nodes import EpisodeType
    except Exception as exc:  # noqa: BLE001
        raise GraphitiBackendUnavailable("graphiti-core EpisodeType is unavailable") from exc
    if kind in {"user_turn", "assistant_turn", "tool_result"}:
        return EpisodeType.message
    if kind in {"source_document", "saved_memory", "background_synthesis"}:
        return EpisodeType.text
    return EpisodeType.text


def _llm_client(config: GraphitiBackendConfig) -> Any:
    from graphiti_core.llm_client import LLMConfig, OpenAIClient

    llm_config = LLMConfig(
        api_key=config.llm_api_key,
        model=config.llm_model,
        small_model=config.llm_small_model,
        base_url=config.llm_base_url,
        temperature=config.llm_temperature,
        max_tokens=config.llm_max_tokens,
    )
    if config.llm_client_kind == "openai_generic":
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

        return OpenAIGenericClient(
            config=llm_config,
            max_tokens=config.llm_max_tokens,
        )
    return OpenAIClient(config=llm_config)


def _embedder(config: GraphitiBackendConfig) -> Any:
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=config.embedding_api_key,
            base_url=config.embedding_base_url,
            embedding_model=config.embedding_model,
            embedding_dim=config.embedding_dim,
        )
    )


def _cross_encoder(config: GraphitiBackendConfig) -> Any:
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from graphiti_core.llm_client import LLMConfig

    return OpenAIRerankerClient(
        config=LLMConfig(
            api_key=config.reranker_api_key or config.llm_api_key,
            model=config.reranker_model or config.llm_small_model or config.llm_model,
            base_url=config.reranker_base_url or config.llm_base_url,
            temperature=0,
            max_tokens=16,
        )
    )


def _graphiti_group_id(namespace: str) -> str:
    import re

    group_id = re.sub(r"[^A-Za-z0-9_]+", "_", namespace).strip("_")
    return group_id or "marvex"


def _graphiti_forget_uuid(ref_id: str) -> str | None:
    try:
        return str(UUID(ref_id))
    except ValueError:
        return None


def _source_from_description(source_description: str) -> dict[str, str]:
    parts = source_description.split(":", 2)
    if len(parts) == 3:
        return {"kind": parts[0], "source_type": parts[1], "source_id": parts[2]}
    return {"kind": "", "source_type": "", "source_id": ""}


class _AsyncRunner:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._closed = False

    def run(self, awaitable: Any) -> Any:
        if self._closed:
            raise RuntimeError("Graphiti async runner is closed")
        future = asyncio.run_coroutine_threadsafe(awaitable, self._loop)
        return future.result()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
        self._loop.close()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


def _utc_now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
