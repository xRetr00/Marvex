from datetime import UTC, datetime

from pydantic import ValidationError

from packages.contracts import ConversationRef, SessionRef


def make_refs():
    return (
        SessionRef(ref_type="session", ref_id="session-memory-001"),
        ConversationRef(ref_type="conversation", ref_id="conversation-memory-001"),
    )


def test_memory_record_accepts_safe_policy_approved_content_only():
    from packages.memory_runtime import MemoryRecord, MemoryRef

    session_ref, conversation_ref = make_refs()
    record = MemoryRecord(
        schema_version="0.1.1-draft",
        memory_ref=MemoryRef(ref_type="memory", ref_id="memory-001"),
        scope="conversation",
        memory_kind="preference",
        session_ref=session_ref,
        conversation_ref=conversation_ref,
        trace_id="trace-memory-test",
        turn_id="turn-memory-test",
        content="User prefers concise engineering status updates.",
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        tags=("communication",),
        raw_transcript_persisted=False,
    )

    assert record.memory_ref.ref_id == "memory-001"
    assert record.content == "User prefers concise engineering status updates."
    assert record.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "memory_ref": {"ref_type": "memory", "ref_id": "memory-001"},
        "scope": "conversation",
        "memory_kind": "preference",
        "session_ref": {"ref_type": "session", "ref_id": "session-memory-001"},
        "conversation_ref": {
            "ref_type": "conversation",
            "ref_id": "conversation-memory-001",
        },
        "trace_id": "trace-memory-test",
        "turn_id": "turn-memory-test",
        "content_preview": "User prefers concise engineering status updates.",
        "write_authorization": "explicit_user",
        "tags": ["communication"],
        "raw_transcript_persisted": False,
    }


def test_memory_record_rejects_raw_transcripts_prompts_and_secret_like_content():
    from packages.memory_runtime import MemoryRecord, MemoryRef

    session_ref, conversation_ref = make_refs()
    unsafe_values = [
        "raw prompt: what is my token",
        "provider output included secret details",
        "full transcript user: hello assistant: hi",
        "Authorization: Bearer secret-token",
    ]

    for content in unsafe_values:
        try:
            MemoryRecord(
                schema_version="0.1.1-draft",
                memory_ref=MemoryRef(ref_type="memory", ref_id="memory-unsafe"),
                scope="conversation",
                memory_kind="fact",
                session_ref=session_ref,
                conversation_ref=conversation_ref,
                trace_id="trace-memory-test",
                turn_id="turn-memory-test",
                content=content,
                write_authorization="policy_approved",
                created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
                tags=(),
                raw_transcript_persisted=False,
            )
        except ValidationError:
            pass
        else:
            raise AssertionError(f"MemoryRecord accepted unsafe content: {content!r}")


def test_memory_write_candidate_is_pending_by_default_and_projection_is_body_free():
    from packages.memory_runtime import MemoryWriteCandidate

    session_ref, conversation_ref = make_refs()
    candidate = MemoryWriteCandidate(
        schema_version="0.1.1-draft",
        candidate_id="candidate-001",
        scope="conversation",
        memory_kind="fact",
        session_ref=session_ref,
        conversation_ref=conversation_ref,
        trace_id="trace-memory-test",
        turn_id="turn-memory-test",
        proposed_content="User is building Marvex memory foundation.",
        source="manual",
        policy_status="pending",
        raw_transcript_persisted=False,
    )

    assert candidate.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "candidate_id": "candidate-001",
        "scope": "conversation",
        "memory_kind": "fact",
        "session_ref": {"ref_type": "session", "ref_id": "session-memory-001"},
        "conversation_ref": {
            "ref_type": "conversation",
            "ref_id": "conversation-memory-001",
        },
        "trace_id": "trace-memory-test",
        "turn_id": "turn-memory-test",
        "source": "manual",
        "policy_status": "pending",
        "raw_transcript_persisted": False,
    }
    assert "User is building" not in repr(candidate.safe_projection())


def test_memory_read_result_contains_refs_and_safe_projections_not_transcripts():
    from packages.memory_runtime import MemoryReadResult, MemoryRecord, MemoryRef

    session_ref, conversation_ref = make_refs()
    record = MemoryRecord(
        schema_version="0.1.1-draft",
        memory_ref=MemoryRef(ref_type="memory", ref_id="memory-001"),
        scope="conversation",
        memory_kind="fact",
        session_ref=session_ref,
        conversation_ref=conversation_ref,
        trace_id="trace-memory-test",
        turn_id="turn-memory-test",
        content="User prefers explicit validation summaries.",
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        tags=("validation",),
        raw_transcript_persisted=False,
    )

    result = MemoryReadResult(
        schema_version="0.1.1-draft",
        query_ref="query-001",
        records=(record,),
        truncated=False,
    )

    projection = result.safe_projection()
    assert projection["record_count"] == 1
    assert projection["records"][0]["memory_ref"] == {
        "ref_type": "memory",
        "ref_id": "memory-001",
    }
    assert "full transcript" not in repr(projection).lower()

