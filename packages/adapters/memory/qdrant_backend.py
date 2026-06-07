"""Qdrant/FastEmbed-backed semantic memory adapter."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from packages.memory_service_runtime.models import (
    MemoryEpisode,
    MemoryEvidenceRef,
    MemoryRankingSignal,
    MemorySourceAttribution,
    bounded_preview,
    make_evidence_id,
)


class QdrantBackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class QdrantMemoryBackendConfig:
    collection_name: str = "marvex_memory"
    path: str = ".marvex-memory/qdrant"
    embedding_model: str = "BAAI/bge-small-en-v1.5"


class QdrantMemoryVectorStore:
    def __init__(self, config: QdrantMemoryBackendConfig, *, client: Any | None = None) -> None:
        self._config = config
        self._client = client
        self._documents_by_id: dict[str, MemoryEpisode] = {}
        self._embedding_model: Any | None = None

    def upsert_episode(self, episode: MemoryEpisode) -> None:
        self._documents_by_id[episode.episode_id] = episode
        client = self._client_or_raise()
        vector = self._embed(episode.content)
        self._ensure_collection(client, vector_size=len(vector))
        metadata = {
            "episode_id": episode.episode_id,
            "namespace": episode.namespace,
            "kind": episode.kind,
            "source_id": episode.source.source_id,
            "source_type": episode.source.source_type,
            "title": episode.source.title,
            "captured_at": episode.occurred_at.isoformat(),
            "uri": episode.source.uri,
            "document": episode.content,
        }
        from qdrant_client import models

        client.upsert(
            collection_name=self._config.collection_name,
            points=[
                models.PointStruct(
                    id=_point_id(episode.episode_id),
                    vector=vector,
                    payload=metadata,
                )
            ],
        )

    def search(self, query: str, *, namespace: str, max_results: int) -> tuple[MemoryEvidenceRef, ...]:
        client = self._client_or_raise()
        query_vector = self._embed(query)
        self._ensure_collection(client, vector_size=len(query_vector))
        from qdrant_client import models

        try:
            response = client.query_points(
                collection_name=self._config.collection_name,
                query=query_vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="namespace",
                            match=models.MatchValue(value=namespace),
                        )
                    ]
                ),
                limit=max_results * 2,
                with_payload=True,
            )
        except Exception:
            return ()
        refs: list[MemoryEvidenceRef] = []
        raw_results = tuple(getattr(response, "points", ()) or ())
        for rank, item in enumerate(raw_results):
            metadata = _metadata(item)
            document = str(getattr(item, "document", "") or metadata.get("document") or "")
            if not document.strip():
                episode = self._documents_by_id.get(str(metadata.get("episode_id", "")))
                document = episode.content if episode is not None else ""
            if not document.strip():
                continue
            score = _bounded_score(getattr(item, "score", None), fallback=max(0.0, 1.0 - (rank * 0.08)))
            source_id = str(metadata.get("source_id") or f"qdrant.{rank}")
            source = MemorySourceAttribution(
                source_id=source_id,
                source_type=_source_type(str(metadata.get("source_type") or "chat")),
                title=str(metadata.get("title") or "Memory episode"),
                uri=str(metadata.get("uri") or f"qdrant://{source_id}"),
                captured_at=_parse_dt(metadata.get("captured_at")),
                trust_level="system_observed",
            )
            refs.append(
                MemoryEvidenceRef(
                    evidence_id=make_evidence_id(source_id=source.source_id, content=document),
                    source=source,
                    quote_preview=bounded_preview(document),
                    episode_id=str(metadata.get("episode_id") or "") or None,
                    fact=bounded_preview(document, limit=500),
                    ranking=MemoryRankingSignal(
                        semantic_score=score,
                        graph_score=0.2,
                        recency_score=0.6,
                        trust_score=0.65,
                        explicit_importance=0.5,
                    ),
                )
            )
            if len(refs) >= max_results:
                break
        return tuple(refs)

    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool:
        self._documents_by_id.pop(ref_id, None)
        client = self._client_or_raise()
        try:
            client.delete(collection_name=self._config.collection_name, points_selector=[_point_id(ref_id)])
            return True
        except Exception:
            return False

    def inspect(self, *, namespace: str | None = None, max_records: int = 50) -> tuple[dict[str, object], ...]:
        rows = list(self._inspect_persisted(namespace=namespace, max_records=max_records))
        if rows:
            return tuple(rows[:max_records])
        rows = []
        for episode in self._documents_by_id.values():
            if namespace is not None and episode.namespace != namespace:
                continue
            rows.append(
                {
                    "backend": "qdrant",
                    "episode_id": episode.episode_id,
                    "namespace": episode.namespace,
                    "kind": episode.kind,
                    "source_id": episode.source.source_id,
                    "content_preview": bounded_preview(episode.content, limit=160),
                    "raw_content_persisted": False,
                }
            )
            if len(rows) >= max_records:
                break
        return tuple(rows)

    def _inspect_persisted(self, *, namespace: str | None, max_records: int) -> tuple[dict[str, object], ...]:
        try:
            client = self._client_or_raise()
            scroll_filter = None
            if namespace is not None:
                from qdrant_client import models

                scroll_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="namespace",
                            match=models.MatchValue(value=namespace),
                        )
                    ]
                )
            points, _next_page = client.scroll(
                collection_name=self._config.collection_name,
                scroll_filter=scroll_filter,
                limit=max_records,
                with_payload=True,
            )
        except Exception:
            return ()
        rows: list[dict[str, object]] = []
        for point in tuple(points)[:max_records]:
            metadata = _metadata(point)
            document = str(metadata.get("document") or "")
            rows.append(
                {
                    "backend": "qdrant",
                    "episode_id": str(metadata.get("episode_id") or ""),
                    "namespace": str(metadata.get("namespace") or namespace or ""),
                    "kind": str(metadata.get("kind") or ""),
                    "source_id": str(metadata.get("source_id") or ""),
                    "source_type": str(metadata.get("source_type") or ""),
                    "title": str(metadata.get("title") or ""),
                    "content_preview": bounded_preview(document, limit=160) if document else "",
                    "raw_content_persisted": False,
                }
            )
        return tuple(rows)

    def health(self) -> dict[str, object]:
        return {
            "backend": "qdrant",
            "status": "configured",
            "collection_name": self._config.collection_name,
            "path": str(Path(self._config.path).expanduser()),
            "embedding_model": self._config.embedding_model,
            "qdrant_dependency_available": importlib.util.find_spec("qdrant_client") is not None,
            "fastembed_dependency_available": importlib.util.find_spec("fastembed") is not None,
            "in_memory_document_count": len(self._documents_by_id),
            "raw_content_persisted": False,
        }

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None
        self._embedding_model = None

    def _client_or_raise(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self) -> Any:
        try:
            from qdrant_client import QdrantClient
        except Exception as exc:  # noqa: BLE001
            raise QdrantBackendUnavailable("qdrant-client[fastembed] is not installed") from exc
        path = Path(self._config.path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(path))

    def _embed(self, text: str) -> list[float]:
        if self._embedding_model is None:
            try:
                from fastembed import TextEmbedding
            except Exception as exc:  # noqa: BLE001
                raise QdrantBackendUnavailable("fastembed is not installed") from exc
            self._embedding_model = TextEmbedding(model_name=self._config.embedding_model)
        vector = next(iter(self._embedding_model.embed([text])))
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        return [float(value) for value in values if value == value]

    def _ensure_collection(self, client: Any, *, vector_size: int) -> None:
        try:
            exists = client.collection_exists(self._config.collection_name)
        except Exception:
            exists = False
        if exists:
            return
        from qdrant_client import models

        client.create_collection(
            collection_name=self._config.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )


def _metadata(item: Any) -> dict[str, Any]:
    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    payload = getattr(item, "payload", None)
    if isinstance(payload, dict):
        return payload
    if isinstance(item, dict):
        raw = item.get("metadata") or item.get("payload") or {}
        return raw if isinstance(raw, dict) else {}
    return {}


def _point_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"marvex-memory:{value}"))


def _bounded_score(value: Any, *, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0.0, min(1.0, numeric))


def _parse_dt(value: Any):
    from datetime import UTC, datetime

    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


def _source_type(value: str):
    allowed = {"chat", "saved_memory", "tool", "connector", "document", "synthesis"}
    return value if value in allowed else "chat"
