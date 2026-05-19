from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.memory_tree_runtime.models import MemoryTreeNode, SourceTrustLevel, SourceType

_SYNONYMS = {
    "web": "browser",
    "agent": "automation",
    "permission": "approval",
    "permissions": "approval",
    "current": "recent",
    "fresh": "recent",
    "inbox": "email",
}


class MemorySearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class MemorySearchFilters(MemorySearchModel):
    trust_levels: tuple[SourceTrustLevel, ...] = ()
    entities: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    source_types: tuple[SourceType, ...] = ()
    min_hotness: float = Field(default=0.0, ge=0.0, le=1.0)
    max_age_days: int | None = Field(default=None, ge=0)
    evidence_required: bool = False


class MemorySemanticQuery(MemorySearchModel):
    query: str = Field(..., min_length=1, max_length=400)
    filters: MemorySearchFilters = Field(default_factory=MemorySearchFilters)
    max_results: int = Field(default=5, ge=1, le=20)


@dataclass(frozen=True)
class SemanticMemorySearchResult:
    query: str
    results: tuple[MemoryTreeNode, ...]
    filters_applied: MemorySearchFilters
    search_mode: Literal["local_semantic", "local_fts_fallback"]
    raw_content_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "query": self.query,
            "result_count": len(self.results),
            "filters_applied": self.filters_applied.model_dump(),
            "search_mode": self.search_mode,
            "results": [node.safe_projection() for node in self.results],
            "raw_content_persisted": False,
        }


def semantic_rank_nodes(query: MemorySemanticQuery, nodes: tuple[MemoryTreeNode, ...], *, chunk_metadata: dict[str, dict[str, str]]) -> SemanticMemorySearchResult:
    query_vector = _vectorize(query.query)
    scored: list[tuple[float, MemoryTreeNode]] = []
    for node in nodes:
        if not _passes_filters(node, query.filters, chunk_metadata):
            continue
        haystack = " ".join([node.title, node.summary, " ".join(_metadata(node, chunk_metadata).values())])
        score = _cosine(query_vector, _vectorize(haystack))
        if score > 0 or _filters_present(query.filters):
            scored.append((score + _hotness(node, chunk_metadata) * 0.15, node))
    scored.sort(key=lambda item: item[0], reverse=True)
    mode: Literal["local_semantic", "local_fts_fallback"] = "local_semantic"
    if not scored:
        terms = set(_tokens(query.query))
        for node in nodes:
            if _passes_filters(node, query.filters, chunk_metadata) and any(term in node.summary.lower() or term in node.title.lower() for term in terms):
                scored.append((0.1, node))
        mode = "local_fts_fallback"
    return SemanticMemorySearchResult(query=query.query, results=tuple(node for _, node in scored[: query.max_results]), filters_applied=query.filters, search_mode=mode)


def _filters_present(filters: MemorySearchFilters) -> bool:
    return bool(filters.trust_levels or filters.entities or filters.topics or filters.sources or filters.source_types or filters.min_hotness > 0 or filters.max_age_days is not None or filters.evidence_required)


def _passes_filters(node: MemoryTreeNode, filters: MemorySearchFilters, chunk_metadata: dict[str, dict[str, str]]) -> bool:
    if filters.evidence_required and not node.evidence_links:
        return False
    metadata = _metadata(node, chunk_metadata)
    if filters.sources and not any(link.source_id in filters.sources for link in node.evidence_links):
        return False
    if filters.trust_levels and metadata.get("trust_level") not in {getattr(value, "value", str(value)) for value in filters.trust_levels}:
        return False
    if filters.source_types and metadata.get("source_type") not in {getattr(value, "value", str(value)) for value in filters.source_types}:
        return False
    if filters.entities and metadata.get("entity", "").lower() not in {value.lower() for value in filters.entities}:
        return False
    if filters.topics and metadata.get("topic", "").lower() not in {value.lower() for value in filters.topics}:
        return False
    if _hotness(node, chunk_metadata) < filters.min_hotness:
        return False
    if filters.max_age_days is not None:
        captured = metadata.get("captured_at")
        if captured:
            try:
                captured_at = datetime.fromisoformat(captured)
                if captured_at.tzinfo is None:
                    captured_at = captured_at.replace(tzinfo=UTC)
                if (datetime.now(UTC) - captured_at).days > filters.max_age_days:
                    return False
            except ValueError:
                return False
    return True


def _metadata(node: MemoryTreeNode, chunk_metadata: dict[str, dict[str, str]]) -> dict[str, str]:
    if not node.evidence_links:
        return {}
    return chunk_metadata.get(node.evidence_links[0].chunk_id, {})


def _hotness(node: MemoryTreeNode, chunk_metadata: dict[str, dict[str, str]]) -> float:
    try:
        return float(_metadata(node, chunk_metadata).get("hotness", "0"))
    except ValueError:
        return 0.0


def _vectorize(text: str) -> dict[str, float]:
    vector: dict[str, float] = {}
    for token in _tokens(text):
        token = _SYNONYMS.get(token, token)
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        vector[token] = vector.get(token, 0.0) + 1.0
    return vector


def _tokens(text: str) -> tuple[str, ...]:
    import re

    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
