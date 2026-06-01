from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import time
import uuid

from packages.contracts import ConversationRef, SessionRef


from .models import (
    SafeSessionHandle,
    SafeConversationProjection,
    SafeSessionProjection,
    TurnLinkageMetadata,
)


CURRENT_PROCESS_SCOPE = "current_process"


class CurrentProcessSessionRegistry:
    def __init__(self) -> None:
        self._turns_by_session_ref_id: dict[str, list[TurnLinkageMetadata]] = defaultdict(list)
        self._turns_by_conversation_ref_id: dict[str, list[TurnLinkageMetadata]] = defaultdict(list)

    def record_turn(self, linkage: TurnLinkageMetadata) -> None:
        if linkage.session_ref is not None:
            self._turns_by_session_ref_id[linkage.session_ref.ref_id].append(linkage)
        if linkage.conversation_ref is not None:
            self._turns_by_conversation_ref_id[linkage.conversation_ref.ref_id].append(linkage)

    def read_session_projection(
        self,
        session_ref: SessionRef,
    ) -> SafeSessionProjection | None:
        turn_linkages = tuple(self._turns_by_session_ref_id.get(session_ref.ref_id, ()))
        if not turn_linkages:
            return None
        return SafeSessionProjection(
            schema_version=turn_linkages[-1].schema_version,
            scope=CURRENT_PROCESS_SCOPE,
            session_ref=session_ref,
            conversation_refs=_unique_conversation_refs(turn_linkages),
            turn_count=len(turn_linkages),
            turn_ids=tuple(linkage.turn_id for linkage in turn_linkages),
            trace_ids=tuple(linkage.trace_id for linkage in turn_linkages),
            previous_response_id_seen=any(
                linkage.previous_response_id_present for linkage in turn_linkages
            ),
            transcript_persisted=False,
        )

    def read_conversation_projection(
        self,
        conversation_ref: ConversationRef,
    ) -> SafeConversationProjection | None:
        turn_linkages = tuple(
            self._turns_by_conversation_ref_id.get(conversation_ref.ref_id, ())
        )
        if not turn_linkages:
            return None
        return SafeConversationProjection(
            schema_version=turn_linkages[-1].schema_version,
            scope=CURRENT_PROCESS_SCOPE,
            conversation_ref=conversation_ref,
            session_refs=_unique_session_refs(turn_linkages),
            turn_count=len(turn_linkages),
            turn_ids=tuple(linkage.turn_id for linkage in turn_linkages),
            trace_ids=tuple(linkage.trace_id for linkage in turn_linkages),
            previous_response_id_seen=any(
                linkage.previous_response_id_present for linkage in turn_linkages
            ),
            transcript_persisted=False,
        )


class BackendSessionCoordinator(CurrentProcessSessionRegistry):
    def __init__(
        self,
        *,
        clock: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        super().__init__()
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._id_factory = id_factory or (lambda: f"session-{uuid.uuid4().hex}")
        self._handles_by_session_ref_id: dict[str, SafeSessionHandle] = {}
        self._trace_ids_by_session_ref_id: dict[str, set[str]] = defaultdict(set)

    def create_session(self, *, title: str | None = None) -> SafeSessionHandle:
        session_ref = SessionRef(ref_type="session", ref_id=self._id_factory())
        return self.ensure_session(session_ref, title=title or "New chat")

    def ensure_session(
        self,
        session_ref: SessionRef,
        *,
        title: str | None = None,
    ) -> SafeSessionHandle:
        existing = self._handles_by_session_ref_id.get(session_ref.ref_id)
        if existing is not None:
            if title is not None and existing.turn_count == 0:
                existing = existing.model_copy(update={"title": _safe_title(title)})
                self._handles_by_session_ref_id[session_ref.ref_id] = existing
            return existing
        now = self._clock()
        handle = SafeSessionHandle(
            schema_version="1",
            session_ref=session_ref,
            title=_safe_title(title or f"Session {session_ref.ref_id}"),
            created_at_unix_ms=now,
            updated_at_unix_ms=now,
            turn_count=0,
            trace_count=0,
            transcript_persisted=False,
        )
        self._handles_by_session_ref_id[session_ref.ref_id] = handle
        return handle

    def record_turn(self, linkage: TurnLinkageMetadata) -> None:
        super().record_turn(linkage)
        if linkage.session_ref is None:
            return
        handle = self.ensure_session(linkage.session_ref)
        self._trace_ids_by_session_ref_id[linkage.session_ref.ref_id].add(linkage.trace_id)
        trace_count = len(self._trace_ids_by_session_ref_id[linkage.session_ref.ref_id])
        updated = handle.model_copy(
            update={
                "updated_at_unix_ms": self._clock(),
                "turn_count": handle.turn_count + 1,
                "trace_count": trace_count,
            }
        )
        self._handles_by_session_ref_id[linkage.session_ref.ref_id] = updated

    def list_sessions(self) -> tuple[SafeSessionHandle, ...]:
        return tuple(
            sorted(
                self._handles_by_session_ref_id.values(),
                key=lambda handle: (-handle.updated_at_unix_ms, handle.session_ref.ref_id),
            )
        )

    def rename_session(self, session_id: str, *, title: str) -> SafeSessionHandle | None:
        handle = self._handles_by_session_ref_id.get(session_id)
        if handle is None:
            return None
        updated = handle.model_copy(update={"title": _safe_title(title), "updated_at_unix_ms": self._clock()})
        self._handles_by_session_ref_id[session_id] = updated
        return updated

    def delete_session(self, session_id: str) -> bool:
        existed = self._handles_by_session_ref_id.pop(session_id, None) is not None
        self._trace_ids_by_session_ref_id.pop(session_id, None)
        self._turns_by_session_ref_id.pop(session_id, None)
        return existed

def _unique_conversation_refs(
    turn_linkages: tuple[TurnLinkageMetadata, ...],
) -> tuple[ConversationRef, ...]:
    refs_by_id = {
        linkage.conversation_ref.ref_id: linkage.conversation_ref
        for linkage in turn_linkages
        if linkage.conversation_ref is not None
    }
    return tuple(refs_by_id[key] for key in sorted(refs_by_id))


def _unique_session_refs(
    turn_linkages: tuple[TurnLinkageMetadata, ...],
) -> tuple[SessionRef, ...]:
    refs_by_id = {
        linkage.session_ref.ref_id: linkage.session_ref
        for linkage in turn_linkages
        if linkage.session_ref is not None
    }
    return tuple(refs_by_id[key] for key in sorted(refs_by_id))


def _safe_title(value: str) -> str:
    title = " ".join(value.strip().split())[:80]
    if not title:
        return "New chat"
    return title
