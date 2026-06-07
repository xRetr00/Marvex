from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import MemoryReadQuery, MemoryRef

from .models import (
    MemoryContextBundle,
    MemoryEpisode,
    MemoryEvidenceRef,
    MemoryRankingSignal,
    MemorySearchResult,
    MemorySourceAttribution,
    MemorySynthesis,
    bounded_preview,
    make_episode_id,
    make_evidence_id,
    make_saved_memory_episode_id,
    namespace_for,
    utc_now,
)


class MemoryGraphStore(Protocol):
    def ingest_episode(self, episode: MemoryEpisode) -> None: ...
    def search(self, query: str, *, namespace: str, max_results: int) -> tuple[MemoryEvidenceRef, ...]: ...
    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool: ...
    def inspect(self, *, namespace: str | None = None, max_records: int = 50) -> tuple[dict[str, object], ...]: ...


class MemoryVectorStore(Protocol):
    def upsert_episode(self, episode: MemoryEpisode) -> None: ...
    def search(self, query: str, *, namespace: str, max_results: int) -> tuple[MemoryEvidenceRef, ...]: ...
    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool: ...
    def inspect(self, *, namespace: str | None = None, max_records: int = 50) -> tuple[dict[str, object], ...]: ...


@dataclass(frozen=True)
class MemoryServiceConfig:
    namespace: str = "marvex"
    max_context_results: int = 8
    max_injected_chars: int = 2400
    graph_required: bool = False
    vector_required: bool = False


class MemoryService:
    """Unified Assistant OS memory service.

    Graphiti/FalkorDB owns temporal fact synthesis and provenance-rich graph
    recall. Qdrant/FastEmbed owns local semantic candidate recall. Existing
    MemoryRuntime stores remain a compatibility source, never the primary
    ranking authority when graph/vector adapters are available.
    """

    def __init__(
        self,
        *,
        config: MemoryServiceConfig | None = None,
        graph_store: MemoryGraphStore | None = None,
        vector_store: MemoryVectorStore | None = None,
        compatibility_store: Any | None = None,
    ) -> None:
        self._config = config or MemoryServiceConfig()
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._compatibility_store = compatibility_store

    @property
    def compatibility_store(self) -> Any | None:
        return self._compatibility_store

    def ingest_turn(
        self,
        *,
        turn_input: Any,
        assistant_text: str | None = None,
        tool_results: tuple[dict[str, object], ...] = (),
    ) -> tuple[MemoryEpisode, ...]:
        episodes: list[MemoryEpisode] = []
        if getattr(turn_input, "user_visible_input", None):
            episodes.append(
                self._episode_from_turn(
                    turn_input,
                    kind="user_turn",
                    content=str(turn_input.user_visible_input),
                    title="User turn",
                    trust_level="explicit_user",
                )
            )
        if assistant_text and assistant_text.strip():
            episodes.append(
                self._episode_from_turn(
                    turn_input,
                    kind="assistant_turn",
                    content=assistant_text,
                    title="Assistant answer",
                    trust_level="system_observed",
                )
            )
        for index, result in enumerate(tool_results):
            summary = result.get("summary") or result.get("content_preview") or result.get("result") or result
            episodes.append(
                self._episode_from_turn(
                    turn_input,
                    kind="tool_result",
                    content=bounded_preview(str(summary), limit=1000),
                    title=f"Tool result {index + 1}",
                    trust_level="system_observed",
                    tags=("tool",),
                )
            )
        for episode in episodes:
            self.ingest_episode(episode)
        return tuple(episodes)

    def ingest_episode(self, episode: MemoryEpisode) -> None:
        errors: list[Exception] = []
        if self._graph_store is not None:
            try:
                self._graph_store.ingest_episode(episode)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        if self._vector_store is not None:
            try:
                self._vector_store.upsert_episode(episode)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        if errors and ((self._config.graph_required and self._graph_store is not None) or (self._config.vector_required and self._vector_store is not None)):
            raise errors[0]

    def ingest_memory_record(self, record: Any) -> MemoryEpisode:
        session_ref = getattr(record, "session_ref", None)
        conversation_ref = getattr(record, "conversation_ref", None)
        namespace = namespace_for(session_ref=session_ref, conversation_ref=conversation_ref, default=self._config.namespace)
        memory_ref = getattr(getattr(record, "memory_ref", None), "ref_id", "memory")
        created_at = getattr(record, "created_at", None) or utc_now()
        source = MemorySourceAttribution(
            source_id=f"saved.{memory_ref}",
            source_type="saved_memory",
            title=str(memory_ref),
            uri=f"local://memory/{memory_ref}",
            captured_at=created_at,
            trust_level="explicit_user" if getattr(record, "write_authorization", "") == "explicit_user" else "system_observed",
        )
        episode = MemoryEpisode(
            episode_id=make_saved_memory_episode_id(memory_ref),
            namespace=namespace,
            kind="saved_memory",
            source=source,
            content=str(getattr(record, "content", "")),
            occurred_at=created_at,
            trace_id=getattr(record, "trace_id", None),
            turn_id=getattr(record, "turn_id", None),
            session_ref=session_ref,
            conversation_ref=conversation_ref,
            tags=tuple(getattr(record, "tags", ()) or ()),
            importance=0.9 if getattr(record, "write_authorization", "") == "explicit_user" else 0.7,
        )
        self.ingest_episode(episode)
        return episode

    def retrieve_context(
        self,
        query: str,
        *,
        session_ref: SessionRef | None = None,
        conversation_ref: ConversationRef | None = None,
        max_results: int | None = None,
    ) -> MemoryContextBundle:
        limit = max_results or self._config.max_context_results
        namespace = namespace_for(session_ref=session_ref, conversation_ref=conversation_ref, default=self._config.namespace)
        graph_refs = self._search_backend(
            self._graph_store,
            query,
            namespace=namespace,
            max_results=limit,
            required=self._config.graph_required,
        )
        vector_refs = self._search_backend(
            self._vector_store,
            query,
            namespace=namespace,
            max_results=limit,
            required=self._config.vector_required,
        )
        compatibility_refs = self._compatibility_refs(query, session_ref=session_ref, conversation_ref=conversation_ref, max_results=limit)
        ranked = _rank_and_dedupe(graph_refs + vector_refs + compatibility_refs, max_results=limit)
        synthesis = self.synthesize_background(query=query, namespace=namespace, evidence_refs=ranked)
        injected = _build_injected_context(query=query, evidence_refs=ranked, synthesis=synthesis, max_chars=self._config.max_injected_chars)
        return MemoryContextBundle(
            query=query,
            namespace=namespace,
            evidence_refs=ranked,
            synthesis=synthesis,
            injected_context=injected,
            truncated=len(graph_refs) + len(vector_refs) + len(compatibility_refs) > len(ranked),
        )

    def search(
        self,
        query: str,
        *,
        session_ref: SessionRef | None = None,
        conversation_ref: ConversationRef | None = None,
        max_results: int | None = None,
    ) -> MemorySearchResult:
        bundle = self.retrieve_context(query, session_ref=session_ref, conversation_ref=conversation_ref, max_results=max_results)
        return MemorySearchResult(query=query, evidence_refs=bundle.evidence_refs, truncated=bundle.truncated)

    def synthesize_background(self, *, query: str, namespace: str, evidence_refs: tuple[MemoryEvidenceRef, ...]) -> MemorySynthesis | None:
        if not evidence_refs:
            return None
        facts = [ref.fact or ref.quote_preview for ref in evidence_refs[:4]]
        summary = "Relevant memory: " + " ".join(f"{index + 1}. {bounded_preview(fact, limit=220)}" for index, fact in enumerate(facts))
        return MemorySynthesis(
            synthesis_id=make_evidence_id(source_id=f"synthesis.{namespace}", content=query),
            namespace=namespace,
            summary=summary,
            evidence_ids=tuple(ref.citation_id for ref in evidence_refs[:4]),
            generated_at=utc_now(),
        )

    def forget(self, ref_id: str, *, namespace: str | None = None) -> bool:
        forgotten = False
        forget_ids = _forget_aliases(ref_id)
        if self._graph_store is not None:
            for forget_id in forget_ids:
                forgotten = self._graph_store.forget(forget_id, namespace=namespace) or forgotten
        if self._vector_store is not None:
            for forget_id in forget_ids:
                forgotten = self._vector_store.forget(forget_id, namespace=namespace) or forgotten
        if self._compatibility_store is not None and hasattr(self._compatibility_store, "forget"):
            try:
                forgotten = bool(self._compatibility_store.forget(MemoryRef(ref_type="memory", ref_id=ref_id)).forgotten) or forgotten
            except Exception:
                pass
        return forgotten

    def health(self) -> dict[str, object]:
        backends: list[dict[str, object]] = []
        for backend_name, backend in (("graphiti", self._graph_store), ("qdrant", self._vector_store)):
            if backend is None:
                continue
            try:
                if hasattr(backend, "health"):
                    health = backend.health()
                    projection = health if isinstance(health, dict) else dict(health)
                else:
                    projection = {
                        "backend": backend_name,
                        "status": "configured",
                        "raw_content_persisted": False,
                    }
            except Exception as exc:  # noqa: BLE001
                projection = {
                    "backend": backend_name,
                    "status": "unavailable",
                    "reason": exc.__class__.__name__,
                    "raw_content_persisted": False,
                }
            projection.setdefault("backend", backend_name)
            projection.setdefault("raw_content_persisted", False)
            backends.append(_safe_nested_mapping(projection))
        if self._compatibility_store is not None:
            backends.append(
                {
                    "backend": "compatibility",
                    "status": "configured",
                    "raw_content_persisted": False,
                    "raw_transcript_persisted": False,
                }
            )
        return _safe_nested_mapping(
            {
                "schema_version": "1",
                "status": _aggregate_health_status(backends),
                "namespace": self._config.namespace,
                "backend_count": len(backends),
                "backends": tuple(backends),
                "graph_required": self._config.graph_required,
                "vector_required": self._config.vector_required,
                "raw_content_persisted": False,
            }
        )

    def safe_inspect(self, *, namespace: str | None = None, max_records: int = 50) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for backend_name, backend in (("graphiti", self._graph_store), ("qdrant", self._vector_store)):
            if backend is None:
                continue
            try:
                rows.extend(dict(row, backend=backend_name) for row in backend.inspect(namespace=namespace, max_records=max_records))
            except Exception:
                rows.append({"backend": backend_name, "status": "unavailable", "raw_content_persisted": False})
        if self._compatibility_store is not None and hasattr(self._compatibility_store, "safe_inspect"):
            rows.extend(dict(row, backend="compatibility") for row in self._compatibility_store.safe_inspect(max_records=max_records))
        return tuple(rows[:max_records])

    def memory_query_with_evidence(self, query: str) -> MemorySearchResult:
        return self.search(query, max_results=self._config.max_context_results)

    def close(self) -> None:
        for backend in (self._graph_store, self._vector_store, self._compatibility_store):
            if backend is not None and hasattr(backend, "close"):
                backend.close()

    def _search_backend(
        self,
        backend: MemoryGraphStore | MemoryVectorStore | None,
        query: str,
        *,
        namespace: str,
        max_results: int,
        required: bool,
    ) -> tuple[MemoryEvidenceRef, ...]:
        if backend is None:
            return ()
        try:
            return tuple(backend.search(query, namespace=namespace, max_results=max_results))
        except Exception:
            if required:
                raise
            return ()

    def _compatibility_refs(
        self,
        query: str,
        *,
        session_ref: SessionRef | None,
        conversation_ref: ConversationRef | None,
        max_results: int,
    ) -> tuple[MemoryEvidenceRef, ...]:
        if self._compatibility_store is None or not hasattr(self._compatibility_store, "read"):
            return ()
        refs: list[MemoryEvidenceRef] = []
        scopes: list[tuple[str, SessionRef | None, ConversationRef | None]] = []
        if session_ref is not None:
            scopes.append(("session", session_ref, None))
        if conversation_ref is not None:
            scopes.append(("conversation", None, conversation_ref))
        for scope, scoped_session, scoped_conversation in scopes:
            try:
                result = self._compatibility_store.read(
                    MemoryReadQuery(
                        schema_version="1",
                        query_id=f"memory-service.compat.{scope}",
                        scope=scope,  # type: ignore[arg-type]
                        session_ref=scoped_session,
                        conversation_ref=scoped_conversation,
                        max_records=max_results,
                        policy_status="approved",
                    )
                )
            except Exception:
                continue
            for record in tuple(result.records):
                haystack = f"{record.memory_ref.ref_id} {record.content} {' '.join(record.tags)}".lower()
                if query.lower() not in haystack and not any(term in haystack for term in query.lower().split()):
                    continue
                source = MemorySourceAttribution(
                    source_id=f"compat.{record.memory_ref.ref_id}",
                    source_type="saved_memory",
                    title=record.memory_ref.ref_id,
                    uri=f"local://memory/{record.memory_ref.ref_id}",
                    captured_at=record.created_at,
                    trust_level="explicit_user" if record.write_authorization == "explicit_user" else "system_observed",
                )
                refs.append(
                    MemoryEvidenceRef(
                        evidence_id=make_evidence_id(source_id=source.source_id, content=record.content),
                        source=source,
                        quote_preview=bounded_preview(record.content),
                        episode_id=record.memory_ref.ref_id,
                        fact=bounded_preview(record.content, limit=500),
                        valid_at=record.created_at,
                        ranking=MemoryRankingSignal(
                            semantic_score=0.35,
                            graph_score=0.1,
                            recency_score=0.6,
                            trust_score=0.8,
                            explicit_importance=0.8 if record.write_authorization == "explicit_user" else 0.5,
                        ),
                    )
                )
        return tuple(refs)

    def _episode_from_turn(
        self,
        turn_input: Any,
        *,
        kind: str,
        content: str,
        title: str,
        trust_level: str,
        tags: tuple[str, ...] = (),
    ) -> MemoryEpisode:
        session_ref = getattr(turn_input, "session_ref", None)
        conversation_ref = getattr(turn_input, "conversation_ref", None)
        if conversation_ref is None and session_ref is not None:
            conversation_ref = ConversationRef(ref_type="conversation", ref_id=f"conversation.{session_ref.ref_id}")
        namespace = namespace_for(session_ref=session_ref, conversation_ref=conversation_ref, default=self._config.namespace)
        source = MemorySourceAttribution(
            source_id=f"{kind}.{getattr(turn_input, 'turn_id', 'turn')}",
            source_type="chat" if kind in {"user_turn", "assistant_turn"} else "tool",
            title=title,
            uri=f"local://turn/{getattr(turn_input, 'turn_id', 'unknown')}",
            captured_at=datetime.now(UTC),
            trust_level=trust_level,  # type: ignore[arg-type]
        )
        return MemoryEpisode(
            episode_id=make_episode_id(
                namespace=namespace,
                kind=kind,
                trace_id=getattr(turn_input, "trace_id", None),
                turn_id=getattr(turn_input, "turn_id", None),
                content=content,
            ),
            namespace=namespace,
            kind=kind,  # type: ignore[arg-type]
            source=source,
            content=content,
            occurred_at=source.captured_at,
            trace_id=getattr(turn_input, "trace_id", None),
            turn_id=getattr(turn_input, "turn_id", None),
            session_ref=session_ref,
            conversation_ref=conversation_ref,
            tags=tags,
            importance=0.7 if kind == "user_turn" else 0.5,
        )


def _rank_and_dedupe(refs: tuple[MemoryEvidenceRef, ...], *, max_results: int) -> tuple[MemoryEvidenceRef, ...]:
    by_id: dict[str, MemoryEvidenceRef] = {}
    for ref in refs:
        existing = by_id.get(ref.citation_id)
        if existing is None or ref.ranking.combined_score > existing.ranking.combined_score:
            by_id[ref.citation_id] = ref
    return tuple(sorted(by_id.values(), key=lambda ref: ref.ranking.combined_score, reverse=True)[:max_results])


def _aggregate_health_status(backends: list[dict[str, object]]) -> str:
    if not backends:
        return "unavailable"
    statuses = {str(backend.get("status") or "unknown") for backend in backends}
    if "unavailable" in statuses:
        return "degraded"
    if statuses <= {"configured", "ok", "ready"}:
        return "configured"
    return "degraded"


def _forget_aliases(ref_id: str) -> tuple[str, ...]:
    saved_episode_id = make_saved_memory_episode_id(ref_id)
    if saved_episode_id == ref_id:
        return (ref_id,)
    return (ref_id, saved_episode_id)


def _safe_nested_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            if normalized.startswith("raw_") and item is not False:
                safe[key_text] = False
                continue
            if any(part in normalized for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "access_token")):
                continue
            safe[key_text] = _safe_nested_mapping(item)
        return safe
    if isinstance(value, (list, tuple)):
        return tuple(_safe_nested_mapping(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "[redacted]" if any(part in lowered for part in ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "access_token")) else value
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)


def _build_injected_context(*, query: str, evidence_refs: tuple[MemoryEvidenceRef, ...], synthesis: MemorySynthesis | None, max_chars: int) -> str:
    lines = [f"Memory context for query: {bounded_preview(query, limit=180)}"]
    if synthesis is not None:
        lines.append(synthesis.summary)
    for index, ref in enumerate(evidence_refs[:8], start=1):
        lines.append(f"{index}. [{ref.citation_id}] {ref.fact or ref.quote_preview} (source: {ref.source.title})")
    return bounded_preview("\n".join(lines), limit=max_chars)
