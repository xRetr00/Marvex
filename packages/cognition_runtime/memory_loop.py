from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.capability_runtime import AutonomyAction, AutonomyMode, AutonomyPolicy, PolicyDecision, evaluate_autonomy_action
from packages.connector_runtime import ConnectorCategory, ConnectorRef
from packages.contracts import ConversationRef
from packages.memory_runtime import (
    MemoryPolicyDecision,
    MemoryReadQuery,
    MemoryReadResult,
    MemoryRecord,
    MemoryRef,
    MemoryWriteCandidate,
    SQLiteMemoryStore,
    build_memory_record_from_candidate,
)
from packages.memory_tree_runtime import (
    CanonicalSourceMetadata,
    EvidenceLink,
    MemoryTreeNode,
    SQLiteMemoryTreeIndex,
    canonicalize_source_document,
    chunk_document,
    score_memory_chunk,
    write_document_to_obsidian_vault,
)


@dataclass(frozen=True)
class MemoryLoopEvidenceRef:
    ref_id: str
    source: str
    quote_preview: str
    raw_content_persisted: bool = False


@dataclass(frozen=True)
class MemoryRecallResult:
    read_result: MemoryReadResult
    records: tuple[MemoryRecord, ...]
    evidence_refs: tuple[MemoryLoopEvidenceRef, ...]
    manual_note_count: int
    raw_context_persisted: bool = False


@dataclass(frozen=True)
class MemoryWriteResult:
    written: bool
    policy_audit: Any
    candidate: MemoryWriteCandidate | None
    decision: MemoryPolicyDecision | None
    record: MemoryRecord | None
    revised_memory_ref: str | None = None
    vault_path: str | None = None
    raw_transcript_persisted: bool = False


class LocalMemoryLoop:
    def __init__(
        self,
        *,
        vault_root: str | Path,
        memory_store: Any,
        tree_index: SQLiteMemoryTreeIndex,
        autonomy_policy: AutonomyPolicy | None = None,
    ) -> None:
        self._vault_root = Path(vault_root).expanduser().resolve()
        self._store = memory_store
        self._tree_index = tree_index
        self._policy = autonomy_policy or AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)

    @classmethod
    def open(cls, *, vault_root: str | Path, autonomy_policy: AutonomyPolicy | None = None) -> "LocalMemoryLoop":
        root = Path(vault_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return cls(
            vault_root=root,
            memory_store=SQLiteMemoryStore(memory_db_path=root / "memory.sqlite", local_user_root=root),
            tree_index=SQLiteMemoryTreeIndex(memory_db_path=root / "memory_tree.sqlite", local_user_root=root),
            autonomy_policy=autonomy_policy,
        )

    @property
    def memory_store(self) -> Any:
        return self._store

    @property
    def vault_root(self) -> Path:
        return self._vault_root

    def recall_for_turn(self, turn_input: Any, *, max_records: int = 3) -> MemoryRecallResult:
        if turn_input.session_ref is None:
            empty = MemoryReadResult(schema_version=turn_input.schema_version, query_ref=f"memory-read.{turn_input.turn_id}", records=(), truncated=False)
            return MemoryRecallResult(read_result=empty, records=(), evidence_refs=(), manual_note_count=0)
        query = MemoryReadQuery(
            schema_version=turn_input.schema_version,
            query_id=f"memory-read.{turn_input.turn_id}",
            scope="session",
            session_ref=turn_input.session_ref,
            conversation_ref=None,
            max_records=max_records,
            policy_status="approved",
        )
        result = self._store.read(query)
        records = tuple(result.records)
        refs = tuple(
            MemoryLoopEvidenceRef(
                ref_id=f"memory.evidence.{record.memory_ref.ref_id}",
                source="memory_loop",
                quote_preview=record.content[:160],
            )
            for record in records
        )
        return MemoryRecallResult(read_result=result, records=records, evidence_refs=refs, manual_note_count=0)

    def write_from_turn(self, turn_input: Any) -> MemoryWriteResult:
        text = turn_input.user_visible_input or ""
        derived = _derive_safe_fact(text)
        if derived is None:
            explicit = _derive_explicit_memory(text)
            if explicit is not None:
                return self._write_explicit_memory(turn_input, explicit)

        audit = evaluate_autonomy_action(
            self._policy,
            AutonomyAction(
                action="derived memory auto write",
                resource_type="derived_memory",
                capability="memory_auto_write",
                safe_trace_ref=turn_input.trace_id,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
        if derived is None or audit.decision != PolicyDecision.ALLOW or turn_input.session_ref is None:
            return MemoryWriteResult(written=False, policy_audit=audit, candidate=None, decision=None, record=None)

        conversation_ref = ConversationRef(ref_type="conversation", ref_id=f"conversation.{turn_input.session_ref.ref_id}")
        memory_ref = MemoryRef(ref_type="memory", ref_id=_memory_ref_for(derived.topic))
        revised = self._forget_existing(memory_ref)
        candidate = MemoryWriteCandidate(
            schema_version=turn_input.schema_version,
            candidate_id=f"candidate.{turn_input.turn_id}",
            scope="session",
            memory_kind="fact",
            session_ref=turn_input.session_ref,
            conversation_ref=conversation_ref,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            proposed_content=derived.content,
            source="future_policy",
            policy_status="approved",
            raw_transcript_persisted=False,
        )
        decision = MemoryPolicyDecision(
            schema_version=turn_input.schema_version,
            candidate_id=candidate.candidate_id,
            decision="approved",
            decided_by="future_policy",
            reason_code="policy.matrix.allow",
            approved_memory_ref=memory_ref,
        )
        record = build_memory_record_from_candidate(
            candidate,
            decision=decision,
            created_at=datetime.now(UTC),
            tags=(derived.topic,),
        )
        self._store.write_record(record)
        vault_path = self._ingest_record(record, topic_label=derived.topic_label)
        return MemoryWriteResult(
            written=True,
            policy_audit=audit,
            candidate=candidate,
            decision=decision,
            record=record,
            revised_memory_ref=memory_ref.ref_id if revised else None,
            vault_path=str(vault_path),
        )

    def _write_explicit_memory(self, turn_input: Any, explicit: "_ExplicitMemory") -> MemoryWriteResult:
        audit = evaluate_autonomy_action(
            self._policy,
            AutonomyAction(
                action="explicit user memory write",
                resource_type="explicit_memory",
                capability="memory_explicit_write",
                safe_trace_ref=turn_input.trace_id,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
        if audit.decision != PolicyDecision.ALLOW or turn_input.session_ref is None:
            return MemoryWriteResult(written=False, policy_audit=audit, candidate=None, decision=None, record=None)

        conversation_ref = ConversationRef(ref_type="conversation", ref_id=f"conversation.{turn_input.session_ref.ref_id}")
        memory_ref = MemoryRef(ref_type="memory", ref_id=_explicit_memory_ref_for(explicit.content, turn_input.turn_id))
        candidate = MemoryWriteCandidate(
            schema_version=turn_input.schema_version,
            candidate_id=f"candidate.{turn_input.turn_id}",
            scope="session",
            memory_kind=explicit.memory_kind,
            session_ref=turn_input.session_ref,
            conversation_ref=conversation_ref,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            proposed_content=explicit.content,
            source="manual",
            policy_status="approved",
            raw_transcript_persisted=False,
        )
        decision = MemoryPolicyDecision(
            schema_version=turn_input.schema_version,
            candidate_id=candidate.candidate_id,
            decision="approved",
            decided_by="explicit_user",
            reason_code="policy.explicit_user_memory_write",
            approved_memory_ref=memory_ref,
        )
        record = build_memory_record_from_candidate(
            candidate,
            decision=decision,
            created_at=datetime.now(UTC),
            tags=("explicit", explicit.memory_kind),
        )
        self._store.write_record(record)
        vault_path = self._ingest_record(record, topic_label="Explicit Memory")
        return MemoryWriteResult(
            written=True,
            policy_audit=audit,
            candidate=candidate,
            decision=decision,
            record=record,
            vault_path=str(vault_path),
        )

    def _forget_existing(self, memory_ref: MemoryRef) -> bool:
        try:
            return self._store.forget(memory_ref).forgotten
        except Exception:
            return False

    def _ingest_record(self, record: MemoryRecord, *, topic_label: str) -> Path:
        connector = ConnectorRef(connector_id="manual-memory-loop", category=ConnectorCategory.GENERIC_OAUTH)
        metadata = CanonicalSourceMetadata(
            source_id="memory_loop",
            external_id=record.memory_ref.ref_id,
            uri=f"local://memory/{record.memory_ref.ref_id}",
            title=topic_label,
            connector_ref=connector,
            captured_at=record.created_at,
        )
        document = canonicalize_source_document(
            metadata=metadata,
            markdown_body=f"# {topic_label}\n\n{record.content}\n\n[[{topic_label}]]",
            ingested_at=record.created_at,
        )
        chunks = chunk_document(document, max_chars=900)
        self._tree_index.upsert_document(document)
        self._tree_index.upsert_chunks(chunks)
        for chunk in chunks:
            self._tree_index.upsert_score(
                score_memory_chunk(
                    chunk_id=chunk.chunk_id,
                    source_weight=1.0,
                    recency=1.0,
                    interaction=0.8,
                    entity_topic_boost=0.8,
                )
            )
            node = MemoryTreeNode.summary_node(
                node_id=f"node:{chunk.chunk_id}",
                title=topic_label,
                summary=chunk.markdown,
                evidence_links=(
                    EvidenceLink(
                        document_id=document.document_id,
                        chunk_id=chunk.chunk_id,
                        source_id=document.metadata.source_id,
                        quote_preview=chunk.markdown[:160],
                    ),
                ),
            )
            self._tree_index.upsert_node(node, tree_kind="topic", tree_key=topic_label.lower().replace(" ", "-"))
            self._tree_index.upsert_node(node, tree_kind="source", tree_key=document.metadata.source_id)
        return write_document_to_obsidian_vault(vault_root=self._vault_root, document=document)


@dataclass(frozen=True)
class _DerivedFact:
    topic: str
    topic_label: str
    content: str


@dataclass(frozen=True)
class _ExplicitMemory:
    content: str
    memory_kind: str


def _derive_safe_fact(text: str) -> _DerivedFact | None:
    match = re.search(
        r"(?:remember that|actually,?)\s+my preferred project codename is\s+([A-Za-z][A-Za-z0-9_-]{0,40})",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    codename = match.group(1).strip("., ")
    return _DerivedFact(
        topic="project-codename",
        topic_label="Project Codename",
        content=f"User preferred project codename is {codename}.",
    )


def _derive_explicit_memory(text: str) -> _ExplicitMemory | None:
    value = " ".join(text.strip().split())
    if not value:
        return None
    patterns = (
        r"^\s*remember\s+(?:this|that)[:\s]+(?P<content>.+)$",
        r"^\s*save\s+(?:this|that)\s+to\s+memory[:\s]+(?P<content>.+)$",
        r"^\s*note\s+that[:\s]+(?P<content>.+)$",
        r"^\s*my\s+preference\s+is\s+(?P<content>.+)$",
        r"^\s*i\s+prefer\s+(?P<content>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match is None:
            continue
        content = match.group("content").strip(" :")
        if not content:
            return None
        lowered = value.lower()
        kind = "preference" if "preference" in lowered or lowered.startswith("i prefer") else "fact"
        return _ExplicitMemory(content=content, memory_kind=kind)
    return None


def _memory_ref_for(topic: str) -> str:
    return f"memory.loop.{topic}"


def _explicit_memory_ref_for(content: str, turn_id: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", content.lower())[:6]
    slug = ".".join(words) or "memory"
    return f"memory.explicit.{turn_id}.{slug}"[:160]
