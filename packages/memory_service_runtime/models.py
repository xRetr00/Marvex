from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.contracts import ConversationRef, SessionRef


_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_SECRET_TERMS = (
    "authorization",
    "bearer ",
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "raw prompt",
    "raw transcript",
    "provider output",
)

MemoryEpisodeKind = Literal[
    "user_turn",
    "assistant_turn",
    "tool_result",
    "saved_memory",
    "source_document",
    "background_synthesis",
]
MemorySourceType = Literal["chat", "saved_memory", "tool", "connector", "document", "synthesis"]


class MemoryServiceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemorySourceAttribution(MemoryServiceModel):
    source_id: str = Field(..., min_length=1, max_length=200)
    source_type: MemorySourceType
    title: str = Field(..., min_length=1, max_length=200)
    uri: str | None = Field(default=None, max_length=500)
    captured_at: datetime
    trust_level: Literal["explicit_user", "system_observed", "connector", "synthesis"] = "system_observed"
    raw_content_persisted: Literal[False] = False

    @field_validator("source_id")
    @classmethod
    def _safe_source_id(cls, value: str) -> str:
        return _safe_id(value, "source_id")

    @field_validator("title")
    @classmethod
    def _safe_title(cls, value: str) -> str:
        return _safe_text(value, "title")

    def safe_projection(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "title": self.title,
            "uri": self.uri,
            "captured_at": self.captured_at.isoformat(),
            "trust_level": self.trust_level,
            "raw_content_persisted": False,
        }


class MemoryEpisode(MemoryServiceModel):
    schema_version: str = Field(default="1.0", min_length=1)
    episode_id: str = Field(..., min_length=1, max_length=220)
    namespace: str = Field(..., min_length=1, max_length=160)
    kind: MemoryEpisodeKind
    source: MemorySourceAttribution
    content: str = Field(..., min_length=1, max_length=6000)
    occurred_at: datetime
    trace_id: str | None = Field(default=None, max_length=160)
    turn_id: str | None = Field(default=None, max_length=160)
    session_ref: SessionRef | None = None
    conversation_ref: ConversationRef | None = None
    tags: tuple[str, ...] = ()
    importance: float = Field(default=0.5, ge=0, le=1)
    raw_content_persisted: Literal[False] = False

    @field_validator("episode_id", "namespace")
    @classmethod
    def _safe_required_ids(cls, value: str) -> str:
        return _safe_id(value, "memory episode id")

    @field_validator("trace_id", "turn_id")
    @classmethod
    def _safe_optional_ids(cls, value: str | None) -> str | None:
        return None if value is None else _safe_id(value, "memory trace/turn id")

    @field_validator("content")
    @classmethod
    def _safe_content(cls, value: str) -> str:
        return _safe_text(value, "memory episode content")

    @field_validator("tags")
    @classmethod
    def _safe_tags(cls, tags: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_id(tag, "memory tag") for tag in tags)

    @model_validator(mode="after")
    def _require_scope(self) -> "MemoryEpisode":
        if self.session_ref is None and self.conversation_ref is None:
            raise ValueError("memory episodes require session_ref or conversation_ref")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "namespace": self.namespace,
            "kind": self.kind,
            "source": self.source.safe_projection(),
            "content_preview": bounded_preview(self.content, limit=180),
            "occurred_at": self.occurred_at.isoformat(),
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "session_ref": self.session_ref.model_dump() if self.session_ref else None,
            "conversation_ref": self.conversation_ref.model_dump() if self.conversation_ref else None,
            "tags": list(self.tags),
            "importance": self.importance,
            "raw_content_persisted": False,
        }


class MemoryRankingSignal(MemoryServiceModel):
    semantic_score: float = Field(default=0, ge=0, le=1)
    graph_score: float = Field(default=0, ge=0, le=1)
    recency_score: float = Field(default=0, ge=0, le=1)
    trust_score: float = Field(default=0, ge=0, le=1)
    explicit_importance: float = Field(default=0, ge=0, le=1)

    @property
    def combined_score(self) -> float:
        return round(
            (self.semantic_score * 0.34)
            + (self.graph_score * 0.28)
            + (self.recency_score * 0.16)
            + (self.trust_score * 0.12)
            + (self.explicit_importance * 0.10),
            4,
        )

    def safe_projection(self) -> dict[str, float]:
        return {
            "semantic_score": self.semantic_score,
            "graph_score": self.graph_score,
            "recency_score": self.recency_score,
            "trust_score": self.trust_score,
            "explicit_importance": self.explicit_importance,
            "combined_score": self.combined_score,
        }


class MemoryEvidenceRef(MemoryServiceModel):
    evidence_id: str = Field(..., min_length=1, max_length=240)
    source: MemorySourceAttribution
    quote_preview: str = Field(..., min_length=1, max_length=240)
    episode_id: str | None = Field(default=None, max_length=220)
    fact: str | None = Field(default=None, max_length=500)
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    ranking: MemoryRankingSignal = Field(default_factory=MemoryRankingSignal)
    raw_content_persisted: Literal[False] = False

    @field_validator("evidence_id")
    @classmethod
    def _safe_evidence_id(cls, value: str) -> str:
        return _safe_id(value, "memory evidence id")

    @field_validator("quote_preview", "fact")
    @classmethod
    def _safe_preview(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, "memory evidence text")

    @property
    def citation_id(self) -> str:
        return f"memory.evidence.{self.evidence_id.removeprefix('memory.evidence.')}"

    @property
    def chunk_id(self) -> str:
        return self.evidence_id.removeprefix("memory.evidence.")

    @property
    def source_id(self) -> str:
        return self.source.source_id

    def safe_projection(self) -> dict[str, object]:
        return {
            "evidence_id": self.citation_id,
            "source_id": self.source.source_id,
            "source_type": self.source.source_type,
            "title": self.source.title,
            "uri": self.source.uri,
            "domain": "memory",
            "quote_preview": self.quote_preview,
            "snippet": self.quote_preview,
            "episode_id": self.episode_id,
            "fact": self.fact,
            "valid_at": self.valid_at.isoformat() if self.valid_at else None,
            "invalid_at": self.invalid_at.isoformat() if self.invalid_at else None,
            "ranking": self.ranking.safe_projection(),
            "raw_content_persisted": False,
        }


class MemorySearchResult(MemoryServiceModel):
    query: str = Field(..., min_length=1, max_length=600)
    evidence_refs: tuple[MemoryEvidenceRef, ...]
    truncated: bool = False
    raw_content_persisted: Literal[False] = False

    @property
    def results(self) -> tuple[MemoryEvidenceRef, ...]:
        return self.evidence_refs

    def safe_projection(self) -> dict[str, object]:
        return {
            "query": self.query,
            "results": [ref.safe_projection() for ref in self.evidence_refs],
            "result_count": len(self.evidence_refs),
            "truncated": self.truncated,
            "raw_content_persisted": False,
        }


class MemorySynthesis(MemoryServiceModel):
    synthesis_id: str = Field(..., min_length=1, max_length=220)
    namespace: str = Field(..., min_length=1, max_length=160)
    summary: str = Field(..., min_length=1, max_length=1200)
    evidence_ids: tuple[str, ...]
    generated_at: datetime
    raw_content_persisted: Literal[False] = False

    @field_validator("synthesis_id", "namespace")
    @classmethod
    def _safe_ids(cls, value: str) -> str:
        return _safe_id(value, "memory synthesis id")

    @field_validator("summary")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        return _safe_text(value, "memory synthesis summary")

    def safe_projection(self) -> dict[str, object]:
        return {
            "synthesis_id": self.synthesis_id,
            "namespace": self.namespace,
            "summary": self.summary,
            "evidence_ids": list(self.evidence_ids),
            "generated_at": self.generated_at.isoformat(),
            "raw_content_persisted": False,
        }


class MemoryContextBundle(MemoryServiceModel):
    schema_version: str = Field(default="1.0", min_length=1)
    query: str = Field(..., min_length=1, max_length=600)
    namespace: str = Field(..., min_length=1, max_length=160)
    evidence_refs: tuple[MemoryEvidenceRef, ...]
    synthesis: MemorySynthesis | None = None
    injected_context: str = Field(..., min_length=1, max_length=2400)
    truncated: bool = False
    raw_context_persisted: Literal[False] = False

    @property
    def result_count(self) -> int:
        return len(self.evidence_refs)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "query": self.query,
            "namespace": self.namespace,
            "evidence_refs": [ref.safe_projection() for ref in self.evidence_refs],
            "evidence_ref_count": len(self.evidence_refs),
            "synthesis": self.synthesis.safe_projection() if self.synthesis else None,
            "injected_context": self.injected_context,
            "truncated": self.truncated,
            "raw_context_persisted": False,
        }


def make_episode_id(*, namespace: str, kind: str, trace_id: str | None, turn_id: str | None, content: str) -> str:
    digest = hashlib.sha256(f"{namespace}|{kind}|{trace_id}|{turn_id}|{content}".encode("utf-8")).hexdigest()[:20]
    prefix = _safe_id(f"episode.{namespace}.{kind}", "episode prefix")[:120]
    return f"{prefix}.{digest}"


def make_saved_memory_episode_id(memory_ref_id: str) -> str:
    return _safe_id(f"episode.saved_memory.{memory_ref_id}", "saved memory episode id")[:220]


def make_evidence_id(*, source_id: str, content: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{content}".encode("utf-8")).hexdigest()[:20]
    return _safe_id(f"memory.evidence.{source_id}.{digest}", "evidence id")[:220]


def namespace_for(*, session_ref: SessionRef | None, conversation_ref: ConversationRef | None, default: str = "marvex") -> str:
    if conversation_ref is not None:
        return _safe_id(f"{default}.conversation.{conversation_ref.ref_id}", "memory namespace")[:160]
    if session_ref is not None:
        return _safe_id(f"{default}.session.{session_ref.ref_id}", "memory namespace")[:160]
    return _safe_id(default, "memory namespace")


def bounded_preview(value: str, *, limit: int = 240) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _safe_text(value: str, label: str) -> str:
    if not value.strip():
        raise ValueError(f"{label} must be non-empty")
    lowered = value.lower()
    if any(term in lowered for term in _SECRET_TERMS):
        raise ValueError(f"{label} contains unsafe raw or secret-like text")
    return re.sub(r"\s+", " ", value.strip())


def _safe_id(value: str, label: str) -> str:
    cleaned = value.strip().replace("/", ".").replace("\\", ".")
    if not cleaned:
        raise ValueError(f"{label} must be non-empty")
    safe = "".join(character if character in _SAFE_ID_CHARS else "-" for character in cleaned)
    safe = re.sub(r"-{2,}", "-", safe).strip(".:-_")
    if not safe:
        raise ValueError(f"{label} must contain safe id characters")
    return safe


def utc_now() -> datetime:
    return datetime.now(UTC)
