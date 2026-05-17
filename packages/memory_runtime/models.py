from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.contracts import ConversationRef, SessionRef


_REF_ID_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_UNSAFE_CONTENT_TERMS = (
    "authorization",
    "bearer",
    "full transcript",
    "provider output",
    "raw prompt",
    "raw provider",
    "secret",
    "token",
    "transcript",
)
DEFAULT_PREVIEW_LENGTH = 120

MemoryScope = Literal["session", "conversation"]
MemoryKind = Literal["fact", "preference", "instruction", "summary"]
MemoryWriteAuthorization = Literal["explicit_user", "policy_approved"]
MemoryCandidateSource = Literal["manual", "future_policy"]
MemoryPolicyStatus = Literal["pending", "approved", "rejected"]


class MemoryRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemoryRef(MemoryRuntimeModel):
    ref_type: Literal["memory"]
    ref_id: str = Field(..., min_length=1)

    @field_validator("ref_id")
    @classmethod
    def _validate_ref_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory ref_id must be non-empty")
        if value != value.strip():
            raise ValueError("memory ref_id must not include surrounding whitespace")
        if any(character not in _REF_ID_SAFE_CHARS for character in value):
            raise ValueError("memory ref_id must contain only safe id characters")
        return value


class MemoryRecord(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    memory_ref: MemoryRef
    scope: MemoryScope
    memory_kind: MemoryKind
    session_ref: SessionRef | None
    conversation_ref: ConversationRef | None
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    write_authorization: MemoryWriteAuthorization
    created_at: datetime
    tags: tuple[str, ...] = ()
    raw_transcript_persisted: Literal[False] = False

    @field_validator("content")
    @classmethod
    def _validate_safe_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory content must be non-empty")
        lowered = value.lower()
        if any(term in lowered for term in _UNSAFE_CONTENT_TERMS):
            raise ValueError("memory content contains unsafe raw or secret-like text")
        return value

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, tags: tuple[str, ...]) -> tuple[str, ...]:
        for tag in tags:
            if not tag.strip() or tag != tag.strip():
                raise ValueError("memory tags must be non-empty and trimmed")
            if any(character not in _REF_ID_SAFE_CHARS for character in tag):
                raise ValueError("memory tags must contain only safe id characters")
        return tags

    @model_validator(mode="after")
    def _validate_scope_ref(self) -> MemoryRecord:
        if self.scope == "session" and self.session_ref is None:
            raise ValueError("session-scoped memory requires session_ref")
        if self.scope == "conversation" and self.conversation_ref is None:
            raise ValueError("conversation-scoped memory requires conversation_ref")
        if self.raw_transcript_persisted is not False:
            raise ValueError("raw_transcript_persisted must remain false")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "memory_ref": _dump_ref(self.memory_ref),
            "scope": self.scope,
            "memory_kind": self.memory_kind,
            "session_ref": _dump_ref(self.session_ref),
            "conversation_ref": _dump_ref(self.conversation_ref),
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "content_preview": _bounded_preview(self.content),
            "write_authorization": self.write_authorization,
            "tags": list(self.tags),
            "raw_transcript_persisted": False,
        }


class MemoryWriteCandidate(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    scope: MemoryScope
    memory_kind: MemoryKind
    session_ref: SessionRef | None
    conversation_ref: ConversationRef | None
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    proposed_content: str = Field(..., min_length=1)
    source: MemoryCandidateSource
    policy_status: MemoryPolicyStatus
    raw_transcript_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_candidate(self) -> MemoryWriteCandidate:
        if self.source != "manual" and self.policy_status == "approved":
            raise ValueError("non-manual memory candidates cannot be approved here")
        if self.raw_transcript_persisted is not False:
            raise ValueError("raw_transcript_persisted must remain false")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "scope": self.scope,
            "memory_kind": self.memory_kind,
            "session_ref": _dump_ref(self.session_ref),
            "conversation_ref": _dump_ref(self.conversation_ref),
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "source": self.source,
            "policy_status": self.policy_status,
            "raw_transcript_persisted": False,
        }


class MemoryReadResult(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    query_ref: str = Field(..., min_length=1)
    records: tuple[MemoryRecord, ...]
    truncated: bool

    @property
    def record_count(self) -> int:
        return len(self.records)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "query_ref": self.query_ref,
            "records": [record.safe_projection() for record in self.records],
            "record_count": self.record_count,
            "truncated": self.truncated,
        }


class MemoryForgetResult(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    memory_ref: MemoryRef
    forgotten: bool

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "memory_ref": _dump_ref(self.memory_ref),
            "forgotten": self.forgotten,
        }


def _dump_ref(ref: MemoryRef | SessionRef | ConversationRef | None) -> dict[str, str] | None:
    if ref is None:
        return None
    return ref.model_dump()


def _bounded_preview(content: str) -> str:
    if len(content) <= DEFAULT_PREVIEW_LENGTH:
        return content
    return f"{content[: DEFAULT_PREVIEW_LENGTH - 3]}..."

