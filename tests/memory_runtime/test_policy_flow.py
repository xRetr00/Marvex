from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.contracts import ConversationRef, SessionRef


def make_candidate(policy_status="pending"):
    from packages.memory_runtime import MemoryWriteCandidate

    return MemoryWriteCandidate(
        schema_version="0.1.1-draft",
        candidate_id="candidate-policy-001",
        scope="conversation",
        memory_kind="preference",
        session_ref=SessionRef(ref_type="session", ref_id="session-policy-001"),
        conversation_ref=ConversationRef(
            ref_type="conversation",
            ref_id="conversation-policy-001",
        ),
        trace_id="trace-policy-001",
        turn_id="turn-policy-001",
        proposed_content="User prefers validation evidence before completion claims.",
        source="manual",
        policy_status=policy_status,
        raw_transcript_persisted=False,
    )


def test_policy_decision_projection_excludes_candidate_body():
    from packages.memory_runtime import MemoryPolicyDecision, MemoryRef

    decision = MemoryPolicyDecision(
        schema_version="0.1.1-draft",
        candidate_id="candidate-policy-001",
        decision="approved",
        decided_by="explicit_user",
        reason_code="user_confirmed",
        approved_memory_ref=MemoryRef(ref_type="memory", ref_id="memory-policy-001"),
    )

    assert decision.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "candidate_id": "candidate-policy-001",
        "decision": "approved",
        "decided_by": "explicit_user",
        "reason_code": "user_confirmed",
        "approved_memory_ref": {"ref_type": "memory", "ref_id": "memory-policy-001"},
    }


def test_approved_policy_decision_builds_memory_record_from_candidate():
    from packages.memory_runtime import (
        MemoryPolicyDecision,
        MemoryRef,
        build_memory_record_from_candidate,
    )

    record = build_memory_record_from_candidate(
        make_candidate(policy_status="approved"),
        decision=MemoryPolicyDecision(
            schema_version="0.1.1-draft",
            candidate_id="candidate-policy-001",
            decision="approved",
            decided_by="explicit_user",
            reason_code="user_confirmed",
            approved_memory_ref=MemoryRef(ref_type="memory", ref_id="memory-policy-001"),
        ),
        created_at=datetime(2026, 5, 17, 12, 30, tzinfo=UTC),
        tags=("validation",),
    )

    assert record.memory_ref.ref_id == "memory-policy-001"
    assert record.write_authorization == "explicit_user"
    assert record.safe_projection()["content_preview"] == (
        "User prefers validation evidence before completion claims."
    )


def test_rejected_policy_decision_cannot_build_memory_record():
    from packages.memory_runtime import MemoryPolicyDecision, build_memory_record_from_candidate

    with pytest.raises(ValueError, match="approved policy decision"):
        build_memory_record_from_candidate(
            make_candidate(policy_status="pending"),
            decision=MemoryPolicyDecision(
                schema_version="0.1.1-draft",
                candidate_id="candidate-policy-001",
                decision="rejected",
                decided_by="future_policy",
                reason_code="insufficient_consent",
                approved_memory_ref=None,
            ),
            created_at=datetime(2026, 5, 17, 12, 30, tzinfo=UTC),
        )


def test_read_query_and_forget_request_require_approval():
    from packages.memory_runtime import MemoryForgetRequest, MemoryReadQuery, MemoryRef

    with pytest.raises(ValidationError):
        MemoryReadQuery(
            schema_version="0.1.1-draft",
            query_id="read-001",
            scope="conversation",
            session_ref=None,
            conversation_ref=ConversationRef(
                ref_type="conversation",
                ref_id="conversation-policy-001",
            ),
            max_records=5,
            policy_status="pending",
        )

    with pytest.raises(ValidationError):
        MemoryForgetRequest(
            schema_version="0.1.1-draft",
            request_id="forget-001",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory-policy-001"),
            policy_status="pending",
        )


def test_store_read_and_forget_request_paths_are_policy_authorized():
    from packages.memory_runtime import (
        CurrentProcessMemoryStore,
        MemoryForgetRequest,
        MemoryPolicyDecision,
        MemoryReadQuery,
        MemoryRef,
        build_memory_record_from_candidate,
    )

    memory_ref = MemoryRef(ref_type="memory", ref_id="memory-policy-001")
    conversation_ref = ConversationRef(
        ref_type="conversation",
        ref_id="conversation-policy-001",
    )
    record = build_memory_record_from_candidate(
        make_candidate(policy_status="approved"),
        decision=MemoryPolicyDecision(
            schema_version="0.1.1-draft",
            candidate_id="candidate-policy-001",
            decision="approved",
            decided_by="explicit_user",
            reason_code="user_confirmed",
            approved_memory_ref=memory_ref,
        ),
        created_at=datetime(2026, 5, 17, 12, 30, tzinfo=UTC),
    )
    store = CurrentProcessMemoryStore()
    store.write_record(record)

    read_result = store.read(
        MemoryReadQuery(
            schema_version="0.1.1-draft",
            query_id="read-001",
            scope="conversation",
            session_ref=None,
            conversation_ref=conversation_ref,
            max_records=5,
            policy_status="approved",
        )
    )
    forget_result = store.forget_by_request(
        MemoryForgetRequest(
            schema_version="0.1.1-draft",
            request_id="forget-001",
            memory_ref=memory_ref,
            policy_status="approved",
        )
    )

    assert read_result.record_count == 1
    assert forget_result.forgotten is True
    assert store.read_by_conversation(conversation_ref).record_count == 0
