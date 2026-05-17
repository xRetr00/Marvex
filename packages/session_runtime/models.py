from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.contracts import AssistantTurnInput, ConversationRef, SessionRef


JsonProjection = dict[str, object]


class SessionRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TurnLinkageMetadata(SessionRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    session_ref: SessionRef | None
    conversation_ref: ConversationRef | None
    previous_response_id_present: bool
    transcript_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _reject_transcript_persistence(self) -> TurnLinkageMetadata:
        if self.transcript_persisted is not False:
            raise ValueError("transcript_persisted must remain false")
        return self

    def safe_projection(self) -> JsonProjection:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "session_ref": _dump_ref(self.session_ref),
            "conversation_ref": _dump_ref(self.conversation_ref),
            "previous_response_id_present": self.previous_response_id_present,
            "transcript_persisted": False,
        }


class SafeSessionProjection(SessionRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    scope: Literal["current_process"]
    session_ref: SessionRef
    conversation_refs: tuple[ConversationRef, ...]
    turn_count: int = Field(..., ge=0)
    turn_ids: tuple[str, ...]
    trace_ids: tuple[str, ...]
    previous_response_id_seen: bool
    transcript_persisted: Literal[False] = False

    def safe_projection(self) -> JsonProjection:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "session_ref": _dump_ref(self.session_ref),
            "conversation_refs": [_dump_ref(ref) for ref in self.conversation_refs],
            "turn_count": self.turn_count,
            "turn_ids": list(self.turn_ids),
            "trace_ids": list(self.trace_ids),
            "previous_response_id_seen": self.previous_response_id_seen,
            "transcript_persisted": False,
        }


class SafeConversationProjection(SessionRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    scope: Literal["current_process"]
    conversation_ref: ConversationRef
    session_refs: tuple[SessionRef, ...]
    turn_count: int = Field(..., ge=0)
    turn_ids: tuple[str, ...]
    trace_ids: tuple[str, ...]
    previous_response_id_seen: bool
    transcript_persisted: Literal[False] = False

    def safe_projection(self) -> JsonProjection:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "conversation_ref": _dump_ref(self.conversation_ref),
            "session_refs": [_dump_ref(ref) for ref in self.session_refs],
            "turn_count": self.turn_count,
            "turn_ids": list(self.turn_ids),
            "trace_ids": list(self.trace_ids),
            "previous_response_id_seen": self.previous_response_id_seen,
            "transcript_persisted": False,
        }


def _dump_ref(ref: SessionRef | ConversationRef | None) -> dict[str, str] | None:
    if ref is None:
        return None
    return ref.model_dump()


def build_turn_linkage_from_assistant_turn_input(
    turn_input: AssistantTurnInput,
    *,
    conversation_ref: ConversationRef | None = None,
    previous_response_id: str | None = None,
) -> TurnLinkageMetadata:
    return TurnLinkageMetadata(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        session_ref=turn_input.session_ref,
        conversation_ref=conversation_ref,
        previous_response_id_present=bool(previous_response_id),
        transcript_persisted=False,
    )
