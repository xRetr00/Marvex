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
MemoryPolicyDecisionValue = Literal["approved", "rejected"]
MemoryPolicyDecider = Literal["explicit_user", "future_policy"]


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
        if self.source not in {"manual", "future_policy"} and self.policy_status == "approved":
            raise ValueError("memory candidates require an approved source")
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


class MemoryPolicyDecision(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    decision: MemoryPolicyDecisionValue
    decided_by: MemoryPolicyDecider
    reason_code: str = Field(..., min_length=1)
    approved_memory_ref: MemoryRef | None

    @field_validator("reason_code")
    @classmethod
    def _validate_reason_code(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("memory policy reason_code must be non-empty and trimmed")
        if any(character not in _REF_ID_SAFE_CHARS for character in value):
            raise ValueError("memory policy reason_code must contain only safe id characters")
        return value

    @model_validator(mode="after")
    def _validate_decision_ref(self) -> MemoryPolicyDecision:
        if self.decision == "approved" and self.approved_memory_ref is None:
            raise ValueError("approved memory policy decisions require approved_memory_ref")
        if self.decision == "rejected" and self.approved_memory_ref is not None:
            raise ValueError("rejected memory policy decisions must not include approved_memory_ref")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "reason_code": self.reason_code,
            "approved_memory_ref": _dump_ref(self.approved_memory_ref),
        }


class MemoryReadQuery(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    query_id: str = Field(..., min_length=1)
    scope: MemoryScope
    session_ref: SessionRef | None
    conversation_ref: ConversationRef | None
    max_records: int = Field(..., ge=1, le=50)
    policy_status: Literal["approved"]

    @model_validator(mode="after")
    def _validate_scope_ref(self) -> MemoryReadQuery:
        if self.scope == "session" and self.session_ref is None:
            raise ValueError("session-scoped memory reads require session_ref")
        if self.scope == "conversation" and self.conversation_ref is None:
            raise ValueError("conversation-scoped memory reads require conversation_ref")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "query_id": self.query_id,
            "scope": self.scope,
            "session_ref": _dump_ref(self.session_ref),
            "conversation_ref": _dump_ref(self.conversation_ref),
            "max_records": self.max_records,
            "policy_status": self.policy_status,
        }


class MemoryForgetRequest(MemoryRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    request_id: str = Field(..., min_length=1)
    memory_ref: MemoryRef
    policy_status: Literal["approved"]

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "memory_ref": _dump_ref(self.memory_ref),
            "policy_status": self.policy_status,
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


def build_memory_record_from_candidate(
    candidate: MemoryWriteCandidate,
    *,
    decision: MemoryPolicyDecision,
    created_at: datetime,
    tags: tuple[str, ...] = (),
) -> MemoryRecord:
    if candidate.candidate_id != decision.candidate_id:
        raise ValueError("memory policy decision candidate_id must match candidate")
    if candidate.policy_status != "approved" or decision.decision != "approved":
        raise ValueError("approved policy decision is required to build memory records")
    if decision.approved_memory_ref is None:
        raise ValueError("approved policy decision is required to build memory records")

    write_authorization: MemoryWriteAuthorization = (
        "explicit_user" if decision.decided_by == "explicit_user" else "policy_approved"
    )
    return MemoryRecord(
        schema_version=candidate.schema_version,
        memory_ref=decision.approved_memory_ref,
        scope=candidate.scope,
        memory_kind=candidate.memory_kind,
        session_ref=candidate.session_ref,
        conversation_ref=candidate.conversation_ref,
        trace_id=candidate.trace_id,
        turn_id=candidate.turn_id,
        content=candidate.proposed_content,
        write_authorization=write_authorization,
        created_at=created_at,
        tags=tags,
        raw_transcript_persisted=False,
    )
