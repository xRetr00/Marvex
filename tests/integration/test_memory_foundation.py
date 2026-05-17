from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import (
    CurrentProcessMemoryStore,
    MemoryForgetRequest,
    MemoryPolicyDecision,
    MemoryReadQuery,
    MemoryRef,
    MemoryWriteCandidate,
    build_memory_record_from_candidate,
)


def test_memory_foundation_policy_store_projection_and_forget_flow():
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-integration")
    conversation_ref = ConversationRef(
        ref_type="conversation",
        ref_id="conversation-memory-integration",
    )
    candidate = MemoryWriteCandidate(
        schema_version="0.1.1-draft",
        candidate_id="candidate-memory-integration",
        scope="conversation",
        memory_kind="preference",
        session_ref=session_ref,
        conversation_ref=conversation_ref,
        trace_id="trace-memory-integration",
        turn_id="turn-memory-integration",
        proposed_content="User prefers evidence-backed completion reports.",
        source="manual",
        policy_status="approved",
        raw_transcript_persisted=False,
    )
    decision = MemoryPolicyDecision(
        schema_version="0.1.1-draft",
        candidate_id="candidate-memory-integration",
        decision="approved",
        decided_by="explicit_user",
        reason_code="user_confirmed",
        approved_memory_ref=MemoryRef(
            ref_type="memory",
            ref_id="memory-integration-001",
        ),
    )
    store = CurrentProcessMemoryStore()
    store.write_record(
        build_memory_record_from_candidate(
            candidate,
            decision=decision,
            created_at=datetime(2026, 5, 17, 13, 0, tzinfo=UTC),
            tags=("validation",),
        )
    )

    read_result = store.read(
        MemoryReadQuery(
            schema_version="0.1.1-draft",
            query_id="read-memory-integration",
            scope="conversation",
            session_ref=None,
            conversation_ref=conversation_ref,
            max_records=1,
            policy_status="approved",
        )
    )
    projection = read_result.safe_projection()

    assert projection["record_count"] == 1
    assert projection["records"][0]["session_ref"] == {
        "ref_type": "session",
        "ref_id": "session-memory-integration",
    }
    assert projection["records"][0]["conversation_ref"] == {
        "ref_type": "conversation",
        "ref_id": "conversation-memory-integration",
    }
    assert projection["records"][0]["trace_id"] == "trace-memory-integration"
    assert projection["records"][0]["turn_id"] == "turn-memory-integration"
    assert projection["records"][0]["raw_transcript_persisted"] is False
    serialized_projection = repr(projection).lower()
    assert "provider output" not in serialized_projection
    assert "full transcript" not in serialized_projection
    assert "token" not in serialized_projection

    forget_result = store.forget_by_request(
        MemoryForgetRequest(
            schema_version="0.1.1-draft",
            request_id="forget-memory-integration",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory-integration-001"),
            policy_status="approved",
        )
    )

    assert forget_result.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "memory_ref": {"ref_type": "memory", "ref_id": "memory-integration-001"},
        "forgotten": True,
    }
    assert store.read_by_conversation(conversation_ref).record_count == 0


def test_memory_foundation_blocks_pending_access_and_raw_transcript_storage():
    with pytest.raises(ValidationError):
        MemoryReadQuery(
            schema_version="0.1.1-draft",
            query_id="read-memory-blocked",
            scope="session",
            session_ref=SessionRef(ref_type="session", ref_id="session-memory-blocked"),
            conversation_ref=None,
            max_records=1,
            policy_status="pending",
        )

    with pytest.raises(ValidationError):
        MemoryWriteCandidate(
            schema_version="0.1.1-draft",
            candidate_id="candidate-memory-blocked",
            scope="session",
            memory_kind="fact",
            session_ref=SessionRef(ref_type="session", ref_id="session-memory-blocked"),
            conversation_ref=None,
            trace_id="trace-memory-blocked",
            turn_id="turn-memory-blocked",
            proposed_content="full transcript user said secret details",
            source="manual",
            policy_status="approved",
            raw_transcript_persisted=True,
        )
