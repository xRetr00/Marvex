from __future__ import annotations

from collections import defaultdict

from packages.contracts import ConversationRef, SessionRef

from .models import (
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryReadQuery,
    MemoryReadResult,
    MemoryRecord,
    MemoryRef,
)


SCHEMA_VERSION = "0.1.1-draft"


class CurrentProcessMemoryStore:
    def __init__(self) -> None:
        self._records_by_memory_id: dict[str, MemoryRecord] = {}
        self._memory_ids_by_session_ref_id: dict[str, list[str]] = defaultdict(list)
        self._memory_ids_by_conversation_ref_id: dict[str, list[str]] = defaultdict(list)

    def write_record(self, record: MemoryRecord) -> None:
        memory_id = record.memory_ref.ref_id
        if memory_id in self._records_by_memory_id:
            raise ValueError("duplicate memory_ref")

        self._records_by_memory_id[memory_id] = record
        if record.session_ref is not None:
            self._memory_ids_by_session_ref_id[record.session_ref.ref_id].append(memory_id)
        if record.conversation_ref is not None:
            self._memory_ids_by_conversation_ref_id[record.conversation_ref.ref_id].append(memory_id)

    def read_by_session(self, session_ref: SessionRef) -> MemoryReadResult:
        memory_ids = self._memory_ids_by_session_ref_id.get(session_ref.ref_id, [])
        return self._read_result(
            query_ref=f"session:{session_ref.ref_id}",
            memory_ids=memory_ids,
        )

    def read_by_conversation(self, conversation_ref: ConversationRef) -> MemoryReadResult:
        memory_ids = self._memory_ids_by_conversation_ref_id.get(conversation_ref.ref_id, [])
        return self._read_result(
            query_ref=f"conversation:{conversation_ref.ref_id}",
            memory_ids=memory_ids,
        )

    def read(self, query: MemoryReadQuery) -> MemoryReadResult:
        if query.scope == "session":
            if query.session_ref is None:
                raise ValueError("session-scoped memory reads require session_ref")
            memory_ids = self._memory_ids_by_session_ref_id.get(query.session_ref.ref_id, [])
            return self._read_result(
                query_ref=query.query_id,
                memory_ids=memory_ids,
                max_records=query.max_records,
            )

        if query.conversation_ref is None:
            raise ValueError("conversation-scoped memory reads require conversation_ref")
        memory_ids = self._memory_ids_by_conversation_ref_id.get(query.conversation_ref.ref_id, [])
        return self._read_result(
            query_ref=query.query_id,
            memory_ids=memory_ids,
            max_records=query.max_records,
        )

    def forget(self, memory_ref: MemoryRef) -> MemoryForgetResult:
        record = self._records_by_memory_id.pop(memory_ref.ref_id, None)
        if record is not None:
            self._remove_index(memory_ref.ref_id)
        return MemoryForgetResult(
            schema_version=SCHEMA_VERSION,
            memory_ref=memory_ref,
            forgotten=record is not None,
        )

    def forget_by_request(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        return self.forget(request.memory_ref)

    def _read_result(
        self,
        *,
        query_ref: str,
        memory_ids: list[str],
        max_records: int | None = None,
    ) -> MemoryReadResult:
        all_records = tuple(
            self._records_by_memory_id[memory_id]
            for memory_id in memory_ids
            if memory_id in self._records_by_memory_id
        )
        records = all_records if max_records is None else all_records[:max_records]
        return MemoryReadResult(
            schema_version=SCHEMA_VERSION,
            query_ref=query_ref,
            records=records,
            truncated=max_records is not None and len(all_records) > max_records,
        )

    def _remove_index(self, memory_id: str) -> None:
        for index in (
            self._memory_ids_by_session_ref_id,
            self._memory_ids_by_conversation_ref_id,
        ):
            for ref_id, memory_ids in tuple(index.items()):
                index[ref_id] = [item for item in memory_ids if item != memory_id]
                if not index[ref_id]:
                    del index[ref_id]
