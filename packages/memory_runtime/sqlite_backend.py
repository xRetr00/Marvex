from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from packages.contracts import ConversationRef, SessionRef

from .models import MemoryForgetRequest, MemoryForgetResult, MemoryReadQuery, MemoryReadResult, MemoryRecord, MemoryRef
from .store import SCHEMA_VERSION


class SQLiteMemoryStore:
    def __init__(self, *, memory_db_path: str | Path, local_user_root: str | Path | None = None) -> None:
        root = Path(local_user_root).expanduser().resolve() if local_user_root else None
        path = Path(memory_db_path).expanduser().resolve()
        if root is not None and not _is_relative_to(path, root):
            raise ValueError("memory_db_path must be local-user scoped")
        self._path = path
        self._ensure_schema()

    def write_record(self, record: MemoryRecord) -> None:
        record = MemoryRecord.model_validate(record.model_dump(mode="json"))
        payload = json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO memory_records(
                        memory_id, scope, memory_kind, session_ref_id, conversation_ref_id,
                        trace_id, turn_id, created_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.memory_ref.ref_id,
                        record.scope,
                        record.memory_kind,
                        record.session_ref.ref_id if record.session_ref else None,
                        record.conversation_ref.ref_id if record.conversation_ref else None,
                        record.trace_id,
                        record.turn_id,
                        record.created_at.isoformat(),
                        payload,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("duplicate memory_ref") from exc

    def read_by_session(self, session_ref: SessionRef) -> MemoryReadResult:
        records = self._records_where("session_ref_id = ?", (session_ref.ref_id,))
        return MemoryReadResult(schema_version=SCHEMA_VERSION, query_ref=f"session:{session_ref.ref_id}", records=records, truncated=False)

    def read_by_conversation(self, conversation_ref: ConversationRef) -> MemoryReadResult:
        records = self._records_where("conversation_ref_id = ?", (conversation_ref.ref_id,))
        return MemoryReadResult(schema_version=SCHEMA_VERSION, query_ref=f"conversation:{conversation_ref.ref_id}", records=records, truncated=False)

    def read(self, query: MemoryReadQuery) -> MemoryReadResult:
        if query.scope == "session":
            if query.session_ref is None:
                raise ValueError("session-scoped memory reads require session_ref")
            records = self._records_where("session_ref_id = ?", (query.session_ref.ref_id,), limit=query.max_records + 1)
        else:
            if query.conversation_ref is None:
                raise ValueError("conversation-scoped memory reads require conversation_ref")
            records = self._records_where("conversation_ref_id = ?", (query.conversation_ref.ref_id,), limit=query.max_records + 1)
        return MemoryReadResult(
            schema_version=SCHEMA_VERSION,
            query_ref=query.query_id,
            records=records[: query.max_records],
            truncated=len(records) > query.max_records,
        )

    def forget(self, memory_ref: MemoryRef) -> MemoryForgetResult:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memory_records WHERE memory_id = ?", (memory_ref.ref_id,))
        return MemoryForgetResult(schema_version=SCHEMA_VERSION, memory_ref=memory_ref, forgotten=cursor.rowcount > 0)

    def forget_by_request(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        return self.forget(request.memory_ref)

    def safe_inspect(self, *, max_records: int = 50) -> tuple[dict[str, object], ...]:
        records = self._records_where("1 = 1", (), limit=max(1, max_records))
        rows: list[dict[str, object]] = []
        for record in records:
            projection = record.safe_projection()
            rows.append(
                {
                    "memory_ref": record.memory_ref.ref_id,
                    "scope": projection["scope"],
                    "memory_kind": projection["memory_kind"],
                    "session_ref": record.session_ref.ref_id if record.session_ref else None,
                    "conversation_ref": record.conversation_ref.ref_id if record.conversation_ref else None,
                    "content_preview": projection["content_preview"],
                    "tag_count": len(record.tags),
                    "raw_transcript_persisted": False,
                }
            )
        return tuple(rows)

    def _records_where(self, clause: str, params: tuple[Any, ...], *, limit: int | None = None) -> tuple[MemoryRecord, ...]:
        query = f"SELECT payload_json FROM memory_records WHERE {clause} ORDER BY created_at, memory_id"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params = (*params, limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(MemoryRecord.model_validate(json.loads(row[0])) for row in rows)

    def _ensure_schema(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_records(
                    memory_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    memory_kind TEXT NOT NULL,
                    session_ref_id TEXT,
                    conversation_ref_id TEXT,
                    trace_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_records(session_ref_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memory_conversation ON memory_records(conversation_ref_id)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
