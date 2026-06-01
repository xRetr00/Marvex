from __future__ import annotations

from dataclasses import dataclass

from .search import MemorySemanticQuery, SemanticMemorySearchResult, semantic_rank_nodes
from .models import (
    CanonicalMemoryDocument,
    ChunkId,
    DailyDigestNode,
    EntityRef,
    EvidenceLink,
    GlobalMemoryTree,
    MemoryChunk,
    MemoryTreeNode,
    SourceMemoryTree,
    TopicMemoryTree,
    TopicRef,
    TreeTraversalResult,
    traverse_tree,
)


@dataclass(frozen=True)
class MemorySearchResult:
    query: str
    results: tuple[MemoryTreeNode, ...]
    raw_content_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "query": self.query,
            "results": [node.safe_projection() for node in self.results],
        }


@dataclass(frozen=True)
class MemoryDrillDownResult:
    chunk_id: ChunkId
    document_id: str
    source_id: str
    quote_preview: str
    raw_content_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "quote_preview": self.quote_preview,
        }


class MemoryTreeRuntime:
    def __init__(self, *, documents: tuple[CanonicalMemoryDocument, ...], chunks: tuple[MemoryChunk, ...]) -> None:
        self._documents = documents
        self._chunks = chunks
        self._nodes = tuple(self._node_for_chunk(chunk) for chunk in chunks)

    @classmethod
    def with_documents(cls, *, documents: tuple[CanonicalMemoryDocument, ...], chunks: tuple[MemoryChunk, ...]) -> MemoryTreeRuntime:
        return cls(documents=documents, chunks=chunks)

    @classmethod
    def from_sqlite_index(cls, index: object) -> "MemoryTreeRuntime":
        documents = tuple(index.documents()) if hasattr(index, "documents") else ()
        chunks = tuple(index.chunks()) if hasattr(index, "chunks") else ()
        return cls(documents=documents, chunks=chunks)

    def semantic_memory_search(self, query: MemorySemanticQuery) -> SemanticMemorySearchResult:
        metadata = {chunk.chunk_id: chunk.metadata for chunk in self._chunks}
        return semantic_rank_nodes(query, self._nodes, chunk_metadata=metadata)

    def memory_tree_search(self, query: str) -> MemorySearchResult:
        terms = tuple(term.lower() for term in query.split() if term.strip())
        matches = tuple(node for node in self._nodes if any(term in node.summary.lower() or term in node.title.lower() for term in terms))
        return MemorySearchResult(query=query, results=matches or self._nodes[:1])

    def memory_tree_traverse(self, start_node_id: str, *, max_depth: int = 2) -> TreeTraversalResult:
        tree = SourceMemoryTree(source_id=self._nodes[0].evidence_links[0].source_id, root=self._nodes[0], nodes=self._nodes)
        return traverse_tree(tree, start_node_id=start_node_id, max_depth=max_depth)

    def memory_drill_down(self, chunk_id: ChunkId) -> MemoryDrillDownResult:
        chunk = self._chunk(chunk_id)
        return MemoryDrillDownResult(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_id=chunk.source_id,
            quote_preview=chunk.markdown[:120],
        )

    def memory_get_source_tree(self, source_id: str) -> SourceMemoryTree:
        nodes = tuple(node for node in self._nodes if any(link.source_id == source_id for link in node.evidence_links))
        root = nodes[0]
        return SourceMemoryTree(source_id=source_id, root=root, nodes=nodes)

    def memory_get_topic_tree(self, topic_id: str) -> TopicMemoryTree:
        root = self._nodes[0]
        return TopicMemoryTree(topic_ref=TopicRef(topic_id=topic_id, label=topic_id.replace("-", " ").title()), root=root, nodes=self._nodes)

    def memory_get_daily_digest(self, date: str) -> DailyDigestNode:
        chunk = self._chunks[0]
        return MemoryTreeNode(
            node_id=f"daily:{date}",
            title=f"Daily digest {date}",
            summary=f"Daily digest includes {len(self._chunks)} source-grounded chunks.",
            node_kind="daily_digest",
            evidence_links=(self._evidence_for_chunk(chunk),),
        )

    def memory_resolve_entity(self, label: str) -> EntityRef:
        safe = label.strip().lower().replace(" ", "-") or "unknown"
        return EntityRef(entity_id=f"entity:{safe}", label=label.strip() or "unknown")

    def memory_query_with_evidence(self, query: str) -> MemorySearchResult:
        return self.memory_tree_search(query)

    def global_tree(self) -> GlobalMemoryTree:
        digest = self.memory_get_daily_digest("current")
        return GlobalMemoryTree(root=digest, daily_digest_nodes=(digest,))

    def _node_for_chunk(self, chunk: MemoryChunk) -> MemoryTreeNode:
        title = chunk.metadata.get("title", chunk.chunk_id)
        return MemoryTreeNode.summary_node(
            node_id=f"node:{chunk.chunk_id}",
            title=title,
            summary=chunk.markdown,
            evidence_links=(self._evidence_for_chunk(chunk),),
        )

    def _evidence_for_chunk(self, chunk: MemoryChunk) -> EvidenceLink:
        return EvidenceLink(document_id=chunk.document_id, chunk_id=chunk.chunk_id, source_id=chunk.source_id, quote_preview=chunk.markdown[:120])

    def _chunk(self, chunk_id: ChunkId) -> MemoryChunk:
        for chunk in self._chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        raise KeyError(chunk_id)

