"""Agent-callable memory tools.

These tools expose MemoryRuntime through the same model tool-use path as file,
web, and utility tools. They return safe projections only and keep non-explicit
writes as candidates instead of silently persisting them.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import (
    MemoryForgetRequest,
    MemoryPolicyDecision,
    MemoryReadQuery,
    MemoryRecord,
    MemoryRef,
    MemoryWriteCandidate,
    build_memory_record_from_candidate,
)

from .base import Tool, succeeded_result


MemoryToolScope = Literal["session", "conversation", "all"]

_EXPLICIT_REMEMBER_PATTERNS = (
    r"^\s*remember\s+(?:this|that)[:\s]+",
    r"^\s*save\s+(?:this|that)\s+to\s+memory[:\s]+",
    r"^\s*note\s+that[:\s]+",
    r"^\s*my\s+preference\s+is\s+",
    r"^\s*i\s+prefer\s+",
)
_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class MemorySearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., min_length=1, max_length=400)
    scope: MemoryToolScope = "session"
    max_results: int = Field(default=5, ge=1, le=20)
    tags: list[str] = Field(default_factory=list)


class MemoryRememberParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(..., min_length=1, max_length=1000)
    memory_kind: Literal["fact", "preference", "instruction", "summary"] = "fact"
    scope: Literal["session", "conversation"] = "session"
    tags: list[str] = Field(default_factory=list)


class MemoryForgetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_ref: str = Field(..., min_length=1, max_length=160)


class MemoryListRecentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: MemoryToolScope = "session"
    max_results: int = Field(default=10, ge=1, le=50)


class _MemoryTool(Tool):
    ref_prefix: ClassVar[str] = "memory."

    def __init__(
        self,
        *,
        memory_store: Any,
        memory_tree_runtime: Any | None = None,
        session_ref: SessionRef | None = None,
        conversation_ref: ConversationRef | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._memory_tree_runtime = memory_tree_runtime
        self._session_ref = session_ref
        self._conversation_ref = conversation_ref

    def _read_records(self, *, scope: MemoryToolScope, max_results: int) -> tuple[MemoryRecord, ...]:
        if self._memory_store is None or not hasattr(self._memory_store, "read"):
            return ()
        if scope == "conversation" and self._conversation_ref is not None:
            query = MemoryReadQuery(
                schema_version="1",
                query_id="memory-tool-read.conversation",
                scope="conversation",
                session_ref=None,
                conversation_ref=self._conversation_ref,
                max_records=max_results,
                policy_status="approved",
            )
            return tuple(self._memory_store.read(query).records)
        if scope in {"session", "all"} and self._session_ref is not None:
            query = MemoryReadQuery(
                schema_version="1",
                query_id="memory-tool-read.session",
                scope="session",
                session_ref=self._session_ref,
                conversation_ref=None,
                max_records=max_results,
                policy_status="approved",
            )
            return tuple(self._memory_store.read(query).records)
        return ()


class MemorySearchTool(_MemoryTool):
    id: ClassVar[str] = "search"
    name: ClassVar[str] = "Memory search"
    description: ClassVar[str] = "Search approved Marvex memory and return safe previews with memory refs."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.MEDIUM
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = MemorySearchParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = MemorySearchParams.model_validate(request.arguments)
        records = self._read_records(scope=params.scope, max_results=params.max_results)
        query = params.query.lower()
        tags = {tag.lower() for tag in params.tags}
        matched = [
            record
            for record in records
            if _record_matches(record, query=query, tags=tags)
        ][: params.max_results]
        tree_results = _safe_tree_results(self._memory_tree_runtime, params.query, params.max_results)
        results = [_record_projection(record) for record in matched]
        return succeeded_result(
            request,
            {
                "operation": "memory_search",
                "query": params.query,
                "scope": params.scope,
                "result_count": len(results) + len(tree_results),
                "results": results,
                "memory_tree_results": tree_results,
                "raw_memory_content_persisted": False,
            },
        )


class MemoryRememberTool(_MemoryTool):
    id: ClassVar[str] = "remember"
    name: ClassVar[str] = "Remember memory"
    description: ClassVar[str] = "Create an approved memory only when the user explicitly asked Marvex to remember it; otherwise return a pending candidate."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.WRITE_LOCAL
    params_model: ClassVar[type[BaseModel]] = MemoryRememberParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = MemoryRememberParams.model_validate(request.arguments)
        explicit, content = _explicit_memory_content(params.content)
        if params.scope == "session" and self._session_ref is None:
            return succeeded_result(
                request,
                {
                    "operation": "memory_remember",
                    "written": False,
                    "policy_status": "blocked",
                    "reason_code": "memory.session_ref_required",
                    "raw_transcript_persisted": False,
                },
            )
        if params.scope == "conversation" and self._conversation_ref is None:
            return succeeded_result(
                request,
                {
                    "operation": "memory_remember",
                    "written": False,
                    "policy_status": "blocked",
                    "reason_code": "memory.conversation_ref_required",
                    "raw_transcript_persisted": False,
                },
            )
        candidate_id = f"memory-candidate.{request.turn_id}"
        candidate = MemoryWriteCandidate(
            schema_version=request.schema_version,
            candidate_id=candidate_id,
            scope=params.scope,
            memory_kind=params.memory_kind,
            session_ref=self._session_ref if params.scope == "session" else None,
            conversation_ref=self._conversation_ref if params.scope == "conversation" else None,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            proposed_content=content,
            source="manual",
            policy_status="approved" if explicit else "pending",
            raw_transcript_persisted=False,
        )
        if not explicit:
            return succeeded_result(
                request,
                {
                    "operation": "memory_remember",
                    "written": False,
                    "policy_status": "pending",
                    "candidate": candidate.safe_projection(),
                    "raw_transcript_persisted": False,
                },
            )
        memory_ref = MemoryRef(ref_type="memory", ref_id=_memory_ref_id(content, request.turn_id))
        decision = MemoryPolicyDecision(
            schema_version=request.schema_version,
            candidate_id=candidate.candidate_id,
            decision="approved",
            decided_by="explicit_user",
            reason_code="policy.explicit_user_remember",
            approved_memory_ref=memory_ref,
        )
        record = build_memory_record_from_candidate(
            candidate,
            decision=decision,
            created_at=datetime.now(UTC),
            tags=tuple(_safe_tag(tag) for tag in params.tags if _safe_tag(tag)),
        )
        if self._memory_store is None or not hasattr(self._memory_store, "write_record"):
            return succeeded_result(
                request,
                {
                    "operation": "memory_remember",
                    "written": False,
                    "policy_status": "blocked",
                    "reason_code": "memory.store_unavailable",
                    "raw_transcript_persisted": False,
                },
            )
        self._memory_store.write_record(record)
        return succeeded_result(
            request,
            {
                "operation": "memory_remember",
                "written": True,
                "policy_status": "approved",
                "memory_ref": record.memory_ref.ref_id,
                "content_preview": record.safe_projection()["content_preview"],
                "raw_transcript_persisted": False,
            },
        )


class MemoryForgetTool(_MemoryTool):
    id: ClassVar[str] = "forget"
    name: ClassVar[str] = "Forget memory"
    description: ClassVar[str] = "Forget an exact memory ref. Query-based or broad memory deletion is not supported by this auto tool."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.MEDIUM
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.WRITE_LOCAL
    params_model: ClassVar[type[BaseModel]] = MemoryForgetParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = MemoryForgetParams.model_validate(request.arguments)
        memory_ref = MemoryRef(ref_type="memory", ref_id=params.memory_ref)
        if self._memory_store is None or not hasattr(self._memory_store, "forget_by_request"):
            forgotten = False
        else:
            forget = MemoryForgetRequest(
                schema_version=request.schema_version,
                request_id=f"forget.{request.turn_id}",
                memory_ref=memory_ref,
                policy_status="approved",
            )
            forgotten = bool(self._memory_store.forget_by_request(forget).forgotten)
        return succeeded_result(
            request,
            {
                "operation": "memory_forget",
                "memory_ref": memory_ref.ref_id,
                "forgotten": forgotten,
                "raw_memory_content_persisted": False,
            },
        )


class MemoryListRecentTool(_MemoryTool):
    id: ClassVar[str] = "list_recent"
    name: ClassVar[str] = "List recent memories"
    description: ClassVar[str] = "List recent approved memory refs and safe previews."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = MemoryListRecentParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = MemoryListRecentParams.model_validate(request.arguments)
        records = self._read_records(scope=params.scope, max_results=params.max_results)
        results = [_record_projection(record) for record in records[: params.max_results]]
        return succeeded_result(
            request,
            {
                "operation": "memory_list_recent",
                "scope": params.scope,
                "result_count": len(results),
                "results": results,
                "raw_memory_content_persisted": False,
            },
        )


def _record_projection(record: MemoryRecord) -> dict[str, object]:
    projection = record.safe_projection()
    return {
        "memory_ref": record.memory_ref.ref_id,
        "scope": record.scope,
        "memory_kind": record.memory_kind,
        "content_preview": projection["content_preview"],
        "tags": list(record.tags),
        "trace_id": record.trace_id,
        "turn_id": record.turn_id,
        "raw_transcript_persisted": False,
    }


def _record_matches(record: MemoryRecord, *, query: str, tags: set[str]) -> bool:
    haystack = " ".join((record.memory_ref.ref_id, record.content, " ".join(record.tags))).lower()
    if query and query not in haystack:
        return False
    if tags and not tags.intersection({tag.lower() for tag in record.tags}):
        return False
    return True


def _safe_tree_results(memory_tree_runtime: Any | None, query: str, max_results: int) -> list[dict[str, object]]:
    if memory_tree_runtime is None or not hasattr(memory_tree_runtime, "memory_query_with_evidence"):
        return []
    try:
        search = memory_tree_runtime.memory_query_with_evidence(query)
    except Exception:
        return []
    rows: list[dict[str, object]] = []
    for node in tuple(getattr(search, "results", ()) or ())[:max_results]:
        projection = node.safe_projection() if hasattr(node, "safe_projection") else {}
        rows.append(dict(projection) if isinstance(projection, dict) else {"node": str(node)[:160]})
    return rows


def _explicit_memory_content(content: str) -> tuple[bool, str]:
    value = " ".join(content.strip().split())
    for pattern in _EXPLICIT_REMEMBER_PATTERNS:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match:
            stripped = value[match.end() :].strip(" :")
            return True, stripped or value
    return False, value


def _memory_ref_id(content: str, turn_id: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", content.lower())[:6]
    slug = ".".join(words) or "memory"
    return _safe_id(f"memory.tool.{turn_id}.{slug}")[:160]


def _safe_tag(tag: str) -> str:
    return _safe_id(tag.strip().replace(" ", "-").lower())[:80]


def _safe_id(value: str) -> str:
    safe = "".join(character if character in _SAFE_ID_CHARS else "-" for character in value)
    safe = safe.strip(".:-_")
    return safe or "memory"


__all__ = [
    "MemorySearchTool",
    "MemoryRememberTool",
    "MemoryForgetTool",
    "MemoryListRecentTool",
    "MemorySearchParams",
    "MemoryRememberParams",
    "MemoryForgetParams",
    "MemoryListRecentParams",
]
