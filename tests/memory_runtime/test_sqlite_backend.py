from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import MemoryReadQuery, MemoryRecord, MemoryRef
from packages.memory_runtime.sqlite_backend import SQLiteMemoryStore


def _record(memory_id: str = "memory-1") -> MemoryRecord:
    return MemoryRecord(
        schema_version="1",
        memory_ref=MemoryRef(ref_type="memory", ref_id=memory_id),
        scope="session",
        memory_kind="fact",
        session_ref=SessionRef(ref_type="session", ref_id="session-1"),
        conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-1"),
        trace_id="trace-1",
        turn_id="turn-1",
        content="User prefers concise status updates.",
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 18, tzinfo=UTC),
        tags=("preference",),
    )


def test_sqlite_memory_store_writes_reads_and_forgets_safe_records(tmp_path) -> None:
    store = SQLiteMemoryStore(memory_db_path=tmp_path / "memory.sqlite", local_user_root=tmp_path)
    record = _record()

    store.write_record(record)
    result = store.read(
        MemoryReadQuery(
            schema_version="1",
            query_id="query-1",
            scope="session",
            session_ref=record.session_ref,
            conversation_ref=None,
            max_records=10,
            policy_status="approved",
        )
    )
    forgotten = store.forget(record.memory_ref)
    after_forget = store.read_by_session(record.session_ref)

    assert result.record_count == 1
    assert result.safe_projection()["records"][0]["content_preview"] == "User prefers concise status updates."
    assert result.safe_projection()["records"][0]["raw_transcript_persisted"] is False
    assert forgotten.forgotten is True
    assert after_forget.record_count == 0


def test_sqlite_memory_store_rejects_paths_outside_local_root(tmp_path) -> None:
    outside = tmp_path.parent / "outside.sqlite"

    with pytest.raises(ValueError):
        SQLiteMemoryStore(memory_db_path=outside, local_user_root=tmp_path)


def test_sqlite_memory_store_rejects_raw_transcript_like_memory(tmp_path) -> None:
    store = SQLiteMemoryStore(memory_db_path=tmp_path / "memory.sqlite", local_user_root=tmp_path)

    with pytest.raises(ValueError):
        store.write_record(_record().model_copy(update={"content": "full transcript: hidden raw prompt"}))


def test_sqlite_memory_store_safe_inspect_projection_uses_previews_only(tmp_path) -> None:
    store = SQLiteMemoryStore(memory_db_path=tmp_path / "memory.sqlite", local_user_root=tmp_path)
    store.write_record(_record())

    rows = store.safe_inspect(max_records=5)

    assert rows == (
        {
            "memory_ref": "memory-1",
            "scope": "session",
            "memory_kind": "fact",
            "session_ref": "session-1",
            "conversation_ref": "conversation-1",
            "content_preview": "User prefers concise status updates.",
            "tag_count": 1,
            "raw_transcript_persisted": False,
        },
    )
