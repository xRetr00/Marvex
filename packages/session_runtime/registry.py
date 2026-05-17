from __future__ import annotations

from collections import defaultdict

from packages.contracts import ConversationRef, SessionRef


from .models import (
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

