from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import AutoFetchRunSummary, ConnectorRef, ConnectorRuntimeModel, ConnectorSyncRequest, ConnectorSyncResult


class ConnectorPolicyDecision(StrEnum):
    ALLOW = "allow"
    APPROVAL_REQUIRED = "approval_required"
    DENY = "deny"


class ConnectorAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decision: ConnectorPolicyDecision
    reason_code: str
    connector_id: str
    capability: str
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class CanonicalSourceMetadata(ConnectorRuntimeModel):
    source_id: str
    external_id: str
    uri: str
    title: str
    connector_ref: ConnectorRef
    captured_at: datetime


class CanonicalMemoryDocument(ConnectorRuntimeModel):
    document_id: str
    metadata: CanonicalSourceMetadata
    markdown: str = Field(..., min_length=1)
    raw_content_persisted: Literal[False] = False


class MemoryChunk(ConnectorRuntimeModel):
    chunk_id: str
    document_id: str
    markdown: str = Field(..., min_length=1)
    raw_content_persisted: Literal[False] = False


class _MemorySearchResult(ConnectorRuntimeModel):
    results: tuple[MemoryChunk, ...]
    raw_content_persisted: Literal[False] = False


class ConnectorMemoryTreeRuntime(ConnectorRuntimeModel):
    documents: tuple[CanonicalMemoryDocument, ...]
    chunks: tuple[MemoryChunk, ...]
    runtime_contract: str = "MemoryTreeRuntime-compatible safe projection"

    def memory_tree_search(self, query: str) -> _MemorySearchResult:
        tokens = {part for part in query.lower().split() if part}
        matches = tuple(chunk for chunk in self.chunks if tokens and any(token in chunk.markdown.lower() for token in tokens))
        return _MemorySearchResult(results=matches)


class ConnectorSyncRunResult(ConnectorRuntimeModel):
    sync_result: ConnectorSyncResult
    documents: tuple[CanonicalMemoryDocument, ...]
    chunks: tuple[MemoryChunk, ...]
    audit_record: ConnectorAuditRecord
    raw_payload_persisted: Literal[False] = False

    @property
    def memory_tree(self) -> ConnectorMemoryTreeRuntime:
        return ConnectorMemoryTreeRuntime(documents=self.documents, chunks=self.chunks)

    def safe_projection(self) -> dict[str, object]:
        return {
            "sync_result": self.sync_result.safe_projection(),
            "document_count": len(self.documents),
            "chunk_count": len(self.chunks),
            "audit": self.audit_record.safe_projection(),
            "raw_payload_persisted": False,
        }


class ConnectorRuntime:
    def __init__(self, *, connector_ref: ConnectorRef, documents: tuple[tuple[str, str, str], ...], autonomy_policy: object) -> None:
        self._connector_ref = connector_ref
        self._documents = documents
        self._policy = autonomy_policy
        self.untracked_background_sync_started = False

    @classmethod
    def mock(cls, *, connector_ref: ConnectorRef, documents: tuple[tuple[str, str, str], ...], autonomy_policy: object) -> "ConnectorRuntime":
        return cls(connector_ref=connector_ref, documents=documents, autonomy_policy=autonomy_policy)

    def sync(self, request: ConnectorSyncRequest) -> ConnectorSyncRunResult:
        audit = _audit_for_policy(self._policy, connector_id=request.connector_ref.connector_id, capability="live_oauth_sync")
        docs = tuple(canonicalize_source_document(metadata=_metadata(request, external_id, title), markdown_body=body, ingested_at=request.requested_at) for external_id, title, body in self._documents)
        chunks = tuple(chunk for document in docs for chunk in chunk_document(document))
        status = "completed" if audit.decision == ConnectorPolicyDecision.ALLOW else "skipped"
        result = ConnectorSyncResult(request_id=request.request_id, connector_ref=request.connector_ref, status=status, documents_seen=len(self._documents) if status == "completed" else 0, safe_summary=f"Connector sync {status} for {request.connector_ref.connector_id}")
        return ConnectorSyncRunResult(sync_result=result, documents=docs if status == "completed" else (), chunks=chunks if status == "completed" else (), audit_record=audit)

    def run_autofetch(self, *, now: datetime) -> AutoFetchRunSummary:
        audit = _audit_for_policy(self._policy, connector_id=self._connector_ref.connector_id, capability="auto_fetch")
        allowed = audit.decision == ConnectorPolicyDecision.ALLOW
        return AutoFetchRunSummary(
            run_id=f"autofetch.{self._connector_ref.connector_id}",
            connector_ref=self._connector_ref,
            started_at=now,
            completed_at=now,
            status="completed" if allowed else "skipped",
            documents_seen=len(self._documents) if allowed else 0,
            documents_canonicalized=len(self._documents) if allowed else 0,
            chunks_created=len(self._documents) if allowed else 0,
        )


def canonicalize_source_document(*, metadata: CanonicalSourceMetadata, markdown_body: str, ingested_at: datetime) -> CanonicalMemoryDocument:
    del ingested_at
    return CanonicalMemoryDocument(document_id=f"doc.{metadata.source_id}.{metadata.external_id}", metadata=metadata, markdown=markdown_body)


def chunk_document(document: CanonicalMemoryDocument, *, max_chars: int = 900) -> tuple[MemoryChunk, ...]:
    body = document.markdown[:max_chars]
    return (MemoryChunk(chunk_id=f"chunk.{document.document_id}.1", document_id=document.document_id, markdown=body),)


def _metadata(request: ConnectorSyncRequest, external_id: str, title: str) -> CanonicalSourceMetadata:
    return CanonicalSourceMetadata(
        source_id=f"source.{request.connector_ref.connector_id}",
        external_id=external_id,
        uri=f"connector://{request.connector_ref.connector_id}/{external_id}",
        title=title,
        connector_ref=request.connector_ref,
        captured_at=request.requested_at,
    )


def _audit_for_policy(policy: object, *, connector_id: str, capability: str) -> ConnectorAuditRecord:
    matrix = getattr(getattr(policy, "matrix", None), "as_projection", lambda: {})()
    permission = str(getattr(matrix.get(capability, matrix.get("live_oauth_sync", "ask")), "value", matrix.get(capability, "ask")))
    decision = ConnectorPolicyDecision.ALLOW if permission == "allow" else ConnectorPolicyDecision.APPROVAL_REQUIRED if permission == "ask" else ConnectorPolicyDecision.DENY
    return ConnectorAuditRecord(decision=decision, reason_code=f"connector.policy.{decision.value}", connector_id=connector_id, capability=capability)