from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.connector_runtime import ConnectorRef, SourceIngestionPolicy

_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_SECRET_TERMS = ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "access_token")

CanonicalContentId = str
ChunkId = str


class MemoryTreeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class SourceType(StrEnum):
    EMAIL = "email"
    CALENDAR = "calendar"
    DOCUMENT = "document"
    REPOSITORY = "repository"
    CHAT = "chat"
    NOTE = "note"
    GENERIC = "generic"


class SourceConnectorKind(StrEnum):
    GMAIL = "gmail"
    GOOGLE_CALENDAR = "google_calendar"
    GOOGLE_DRIVE = "google_drive"
    GITHUB = "github"
    SLACK = "slack"
    NOTION = "notion"
    GENERIC_OAUTH = "generic_oauth"
    MANUAL = "manual"


class SourceProvenance(StrEnum):
    USER_CONNECTED_ACCOUNT = "user_connected_account"
    USER_IMPORTED_FILE = "user_imported_file"
    MANUAL_ENTRY = "manual_entry"


class SourceTrustLevel(StrEnum):
    USER_APPROVED = "user_approved"
    SYSTEM_OBSERVED = "system_observed"
    UNVERIFIED = "unverified"


class SourcePermissionScope(StrEnum):
    READ_ONLY_METADATA = "read_only_metadata"
    READ_ONLY_METADATA_AND_CONTENT = "read_only_metadata_and_content"


class MemorySourceRef(MemoryTreeModel):
    source_id: str
    source_type: SourceType
    connector_kind: SourceConnectorKind
    provenance: SourceProvenance
    trust_level: SourceTrustLevel
    permission_scope: SourcePermissionScope
    ingestion_policy: SourceIngestionPolicy
    display_name: str = Field(..., min_length=1, max_length=160)
    last_sync_status: str = "never_synced"
    raw_credentials_persisted: Literal[False] = False

    @field_validator("source_id")
    @classmethod
    def _safe_source_id(cls, value: str) -> str:
        return _validate_safe_id(value, "source_id")

    def safe_projection(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "connector_kind": self.connector_kind,
            "provenance": self.provenance,
            "trust_level": self.trust_level,
            "permission_scope": self.permission_scope,
            "display_name": _safe_text(self.display_name),
            "ingestion_policy": self.ingestion_policy.safe_projection(),
            "last_sync_status": self.last_sync_status,
            "raw_credentials_persisted": False,
        }


SafeSourceProjection = dict[str, object]


class CanonicalSourceMetadata(MemoryTreeModel):
    source_id: str
    external_id: str
    uri: str = Field(..., min_length=1, max_length=500)
    title: str = Field(..., min_length=1, max_length=200)
    connector_ref: ConnectorRef
    captured_at: datetime

    @field_validator("source_id", "external_id")
    @classmethod
    def _safe_ids(cls, value: str) -> str:
        if any(part in value.lower() for part in _SECRET_TERMS):
            raise ValueError("metadata ids must not contain secret-like terms")
        return value.strip()


class CanonicalMemoryDocument(MemoryTreeModel):
    document_id: CanonicalContentId
    metadata: CanonicalSourceMetadata
    normalized_markdown: str = Field(..., min_length=1)
    content_hash: str
    ingested_at: datetime
    raw_secret_persisted: Literal[False] = False

    @field_validator("normalized_markdown")
    @classmethod
    def _safe_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("canonical markdown must be non-empty")
        if any(part in value.lower() for part in _SECRET_TERMS):
            raise ValueError("canonical markdown contains secret-like content")
        return value

    def safe_projection(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "source_id": self.metadata.source_id,
            "external_id": self.metadata.external_id,
            "title": _safe_text(self.metadata.title),
            "connector_id": self.metadata.connector_ref.connector_id,
            "content_hash": self.content_hash,
            "ingested_at": self.ingested_at.isoformat(),
            "raw_secret_persisted": False,
        }


class MemoryChunk(MemoryTreeModel):
    chunk_id: ChunkId
    document_id: CanonicalContentId
    source_id: str
    ordinal: int = Field(..., ge=0)
    markdown: str = Field(..., min_length=1)
    char_count: int = Field(..., ge=1)
    content_hash: str
    duplicate_ready_hash: str
    metadata: dict[str, str] = Field(default_factory=dict)
    raw_secret_persisted: Literal[False] = False

    @field_validator("markdown")
    @classmethod
    def _safe_chunk(cls, value: str) -> str:
        if any(part in value.lower() for part in _SECRET_TERMS):
            raise ValueError("memory chunk contains secret-like content")
        return value

    def safe_projection(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "ordinal": self.ordinal,
            "char_count": self.char_count,
            "content_hash": self.content_hash,
            "raw_secret_persisted": False,
        }


class BoundedScore(MemoryTreeModel):
    value: float = Field(..., ge=0, le=1)


class MemoryImportanceScore(BoundedScore):
    pass


class SourceWeight(BoundedScore):
    pass


class RecencyScore(BoundedScore):
    pass


class InteractionScore(BoundedScore):
    pass


class EntityTopicBoost(BoundedScore):
    pass


class KeepDropDecision(MemoryTreeModel):
    decision: Literal["keep", "drop"]
    threshold: float = Field(..., ge=0, le=1)


class ScoringExplanation(MemoryTreeModel):
    chunk_id: ChunkId
    source_weight: SourceWeight
    recency: RecencyScore
    interaction: InteractionScore
    entity_topic_boost: EntityTopicBoost
    importance: MemoryImportanceScore
    keep_drop_decision: KeepDropDecision
    policy_owner: Literal["MemoryTreeRuntime"] = "MemoryTreeRuntime"

    @property
    def explanation(self) -> "ScoringExplanation":
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "source_weight": self.source_weight.value,
            "recency": self.recency.value,
            "interaction": self.interaction.value,
            "entity_topic_boost": self.entity_topic_boost.value,
            "importance": self.importance.value,
            "decision": self.keep_drop_decision.decision,
            "threshold": self.keep_drop_decision.threshold,
            "policy_owner": self.policy_owner,
            "raw_content_persisted": False,
        }


class HotnessSignal(MemoryTreeModel):
    chunk_id: ChunkId
    score: MemoryImportanceScore
    reason_code: str


class EntityRef(MemoryTreeModel):
    entity_id: str
    label: str


class TopicRef(MemoryTreeModel):
    topic_id: str
    label: str


class EntityCandidate(MemoryTreeModel):
    entity_ref: EntityRef
    evidence_chunk_ids: tuple[ChunkId, ...]


class TopicAssignment(MemoryTreeModel):
    topic_ref: TopicRef
    chunk_id: ChunkId
    confidence: float = Field(..., ge=0, le=1)


class EntityConsolidationCandidate(MemoryTreeModel):
    primary_entity_ref: EntityRef
    duplicate_entity_ref: EntityRef
    confidence: float = Field(..., ge=0, le=1)


class DuplicateDetectionSignal(MemoryTreeModel):
    content_hash: str
    candidate_chunk_ids: tuple[ChunkId, ...]


SafeEntityProjection = dict[str, object]
SafeTopicProjection = dict[str, object]


class EvidenceLink(MemoryTreeModel):
    document_id: CanonicalContentId
    chunk_id: ChunkId
    source_id: str
    quote_preview: str = Field(..., min_length=1, max_length=160)

    def safe_projection(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "quote_preview": _safe_text(self.quote_preview),
        }


class MemoryTreeNode(MemoryTreeModel):
    node_id: str
    title: str
    summary: str
    node_kind: Literal["summary", "daily_digest", "source", "topic"]
    parent_node_id: str | None = None
    child_node_ids: tuple[str, ...] = ()
    evidence_links: tuple[EvidenceLink, ...]

    @classmethod
    def summary_node(cls, *, node_id: str, title: str, summary: str, evidence_links: tuple[EvidenceLink, ...]) -> MemoryTreeNode:
        return cls(node_id=node_id, title=title, summary=summary, node_kind="summary", evidence_links=evidence_links)

    @model_validator(mode="after")
    def _require_provenance(self) -> MemoryTreeNode:
        if not self.evidence_links:
            raise ValueError("memory tree nodes require provenance evidence")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "title": _safe_text(self.title),
            "summary": _safe_text(self.summary),
            "node_kind": self.node_kind,
            "parent_node_id": self.parent_node_id,
            "child_node_count": len(self.child_node_ids),
            "evidence_count": len(self.evidence_links),
            "evidence_links": [link.safe_projection() for link in self.evidence_links],
        }


SummaryNode = MemoryTreeNode
DailyDigestNode = MemoryTreeNode


class SourceMemoryTree(MemoryTreeModel):
    source_id: str
    root: MemoryTreeNode
    nodes: tuple[MemoryTreeNode, ...]


class TopicMemoryTree(MemoryTreeModel):
    topic_ref: TopicRef
    root: MemoryTreeNode
    nodes: tuple[MemoryTreeNode, ...]


class GlobalMemoryTree(MemoryTreeModel):
    root: MemoryTreeNode
    daily_digest_nodes: tuple[MemoryTreeNode, ...]


class TreeUpdateSummary(MemoryTreeModel):
    tree_kind: Literal["source", "topic", "global", "daily"]
    nodes_updated: int = Field(..., ge=0)
    evidence_links_added: int = Field(..., ge=0)
    raw_content_persisted: Literal[False] = False


class TreeTraversalResult(MemoryTreeModel):
    tree_kind: str
    start_node_id: str
    nodes: tuple[MemoryTreeNode, ...]
    truncated: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "tree_kind": self.tree_kind,
            "start_node_id": self.start_node_id,
            "nodes": [node.safe_projection() for node in self.nodes],
            "truncated": self.truncated,
            "raw_content_persisted": False,
        }


def canonicalize_source_document(*, metadata: CanonicalSourceMetadata, markdown_body: str, ingested_at: datetime | None = None) -> CanonicalMemoryDocument:
    normalized = _normalize_markdown(markdown_body)
    content_hash = _sha256(normalized)
    document_id = "cmdoc:" + _sha256(f"{metadata.source_id}|{metadata.external_id}|{content_hash}")[:24]
    return CanonicalMemoryDocument(
        document_id=document_id,
        metadata=metadata,
        normalized_markdown=normalized,
        content_hash=content_hash,
        ingested_at=ingested_at or datetime.now(UTC),
    )


def chunk_document(document: CanonicalMemoryDocument, *, max_chars: int = 900) -> tuple[MemoryChunk, ...]:
    if max_chars < 20:
        raise ValueError("max_chars must be at least 20")
    parts = _bounded_parts(document.normalized_markdown, max_chars=max_chars)
    chunks: list[MemoryChunk] = []
    for ordinal, markdown in enumerate(parts):
        content_hash = _sha256(markdown)
        chunk_id = f"chunk:{document.document_id.removeprefix('cmdoc:')}:{ordinal}"
        chunks.append(
            MemoryChunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                source_id=document.metadata.source_id,
                ordinal=ordinal,
                markdown=markdown,
                char_count=len(markdown),
                content_hash=content_hash,
                duplicate_ready_hash=content_hash,
                metadata={"title": document.metadata.title},
            )
        )
    return tuple(chunks)


def score_memory_chunk(*, chunk_id: ChunkId, source_weight: float, recency: float, interaction: float, entity_topic_boost: float) -> ScoringExplanation:
    importance_value = round((source_weight * 0.5) + (recency * 0.2) + (interaction * 0.2) + (entity_topic_boost * 0.1), 2)
    decision = "keep" if importance_value >= 0.5 else "drop"
    return ScoringExplanation(
        chunk_id=chunk_id,
        source_weight=SourceWeight(value=source_weight),
        recency=RecencyScore(value=recency),
        interaction=InteractionScore(value=interaction),
        entity_topic_boost=EntityTopicBoost(value=entity_topic_boost),
        importance=MemoryImportanceScore(value=importance_value),
        keep_drop_decision=KeepDropDecision(decision=decision, threshold=0.5),
    )


def traverse_tree(tree: SourceMemoryTree | TopicMemoryTree | GlobalMemoryTree, *, start_node_id: str, max_depth: int) -> TreeTraversalResult:
    nodes = getattr(tree, "nodes", getattr(tree, "daily_digest_nodes", ()))
    by_id = {node.node_id: node for node in nodes}
    start = by_id.get(start_node_id) or getattr(tree, "root")
    selected = [start]
    if max_depth > 1:
        selected.extend(node for node in nodes if node.parent_node_id == start.node_id)
    kind = "source" if isinstance(tree, SourceMemoryTree) else "topic" if isinstance(tree, TopicMemoryTree) else "global"
    return TreeTraversalResult(tree_kind=kind, start_node_id=start_node_id, nodes=tuple(dict.fromkeys(selected)))


def _normalize_markdown(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _bounded_parts(text: str, *, max_chars: int) -> tuple[str, ...]:
    words = text.split()
    parts: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(word[i : i + max_chars] for i in range(0, len(word), max_chars))
            continue
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            parts.append(current)
            current = word
    if current:
        parts.append(current)
    return tuple(parts or (text[:max_chars],))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_safe_id(value: str, field_name: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and trimmed")
    if any(character not in _SAFE_CHARS for character in value):
        raise ValueError(f"{field_name} contains unsafe characters")
    return value


def _safe_text(value: str) -> str:
    return "[redacted]" if any(part in value.lower() for part in _SECRET_TERMS) else value
