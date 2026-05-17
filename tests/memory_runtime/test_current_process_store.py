from datetime import UTC, datetime

import pytest

from packages.contracts import ConversationRef, SessionRef


def make_record(memory_id="memory-001", *, content="User prefers brief summaries."):
    from packages.memory_runtime import MemoryRecord, MemoryRef

    return MemoryRecord(
        schema_version="0.1.1-draft",
        memory_ref=MemoryRef(ref_type="memory", ref_id=memory_id),
        scope="conversation",
        memory_kind="preference",
        session_ref=SessionRef(ref_type="session", ref_id="session-memory-store"),
        conversation_ref=ConversationRef(
            ref_type="conversation",
            ref_id="conversation-memory-store",
        ),
        trace_id="trace-memory-store",
        turn_id="turn-memory-store",
        content=content,
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        tags=("preference",),
        raw_transcript_persisted=False,
    )


def test_current_process_memory_store_records_and_reads_safe_results():
    from packages.memory_runtime import CurrentProcessMemoryStore

    store = CurrentProcessMemoryStore()
    store.write_record(make_record())

    result = store.read_by_conversation(
        ConversationRef(ref_type="conversation", ref_id="conversation-memory-store")
    )

    projection = result.safe_projection()
    assert projection["schema_version"] == "0.1.1-draft"
    assert projection["query_ref"] == "conversation:conversation-memory-store"
    assert projection["record_count"] == 1
    assert projection["records"][0]["memory_ref"] == {
        "ref_type": "memory",
        "ref_id": "memory-001",
    }
    assert "raw prompt" not in repr(projection).lower()
    assert "full transcript" not in repr(projection).lower()


def test_current_process_memory_store_is_instance_owned_not_global():
    from packages.memory_runtime import CurrentProcessMemoryStore

    first = CurrentProcessMemoryStore()
    second = CurrentProcessMemoryStore()
    first.write_record(make_record())
    conversation_ref = ConversationRef(
        ref_type="conversation",
        ref_id="conversation-memory-store",
    )

    assert first.read_by_conversation(conversation_ref).record_count == 1
    assert second.read_by_conversation(conversation_ref).record_count == 0


def test_current_process_memory_store_rejects_duplicate_memory_ids():
    from packages.memory_runtime import CurrentProcessMemoryStore

    store = CurrentProcessMemoryStore()
    store.write_record(make_record())

    with pytest.raises(ValueError, match="duplicate memory_ref"):
        store.write_record(make_record(content="User prefers detailed summaries."))


def test_forget_removes_record_by_ref_without_exposing_content():
    from packages.memory_runtime import CurrentProcessMemoryStore, MemoryRef

    store = CurrentProcessMemoryStore()
    store.write_record(make_record())


    result = store.forget(MemoryRef(ref_type="memory", ref_id="memory-001"))

    assert result.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "memory_ref": {"ref_type": "memory", "ref_id": "memory-001"},
        "forgotten": True,
    }
    assert store.read_by_conversation(
        ConversationRef(ref_type="conversation", ref_id="conversation-memory-store")
    ).record_count == 0

