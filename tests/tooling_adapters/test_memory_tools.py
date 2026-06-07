from __future__ import annotations

from datetime import UTC, datetime

from packages.adapters.capabilities.tools.memory import (
    MemoryForgetTool,
    MemoryListRecentTool,
    MemoryRememberTool,
    MemorySearchTool,
)
from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.contracts import SessionRef
from packages.memory_runtime import MemoryRecord, MemoryRef
from packages.memory_runtime.store import CurrentProcessMemoryStore


def _request(identifier: str, arguments: dict[str, object]) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=identifier)
    return CapabilityExecutionRequest(
        schema_version="1",
        request_id=f"request.{identifier}",
        trace_id="trace-memory-tool",
        turn_id="turn-memory-tool",
        proposal=CapabilityCallProposal(
            schema_version="1",
            proposal_id=f"proposal.{identifier}",
            trace_id="trace-memory-tool",
            turn_id="turn-memory-tool",
            capability_ref=ref,
            proposed_action=identifier,
            risk_level=ToolRiskLevel.SAFE,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
            arguments_schema={"type": "object"},
        ),
        permission_decision=CapabilityPermissionDecision(
            schema_version="1",
            decision_id=f"permission.{identifier}",
            capability_ref=ref,
            decision="approved",
            reason_code="policy_allowlisted_safe_tool",
            human_approval=HumanApprovalRequirement(
                required=False,
                reason_code="not_required",
                prompt_user_visible=False,
            ),
        ),
        arguments=arguments,
    )


def test_memory_remember_explicit_user_signal_writes_safe_record() -> None:
    store = CurrentProcessMemoryStore()
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-tool")
    tool = MemoryRememberTool(memory_store=store, session_ref=session_ref)

    result = tool.execute(
        _request(
            "memory.remember",
            {
                "content": "remember this: User prefers concise answers.",
                "memory_kind": "preference",
                "scope": "session",
                "tags": ["preference"],
            },
        )
    )

    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "memory_remember"
    assert result.safe_result["written"] is True
    assert result.safe_result["policy_status"] == "approved"
    remembered = store.read_by_session(session_ref)
    assert remembered.record_count == 1
    assert remembered.records[0].content == "User prefers concise answers."


def test_memory_remember_explicit_user_signal_mirrors_to_memory_service() -> None:
    class Service:
        def __init__(self) -> None:
            self.records = []

        def ingest_memory_record(self, record):
            self.records.append(record)

            class Episode:
                def safe_projection(self):
                    return {
                        "episode_id": "episode.saved.memory",
                        "kind": "saved_memory",
                        "raw_content_persisted": False,
                    }

            return Episode()

    store = CurrentProcessMemoryStore()
    service = Service()
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-tool")
    tool = MemoryRememberTool(memory_store=store, memory_service=service, session_ref=session_ref)

    result = tool.execute(
        _request(
            "memory.remember",
            {
                "content": "remember this: User prefers concise answers.",
                "memory_kind": "preference",
                "scope": "session",
            },
        )
    )

    assert result.status == "succeeded"
    assert result.safe_result["written"] is True
    assert result.safe_result["memory_service_episode"]["kind"] == "saved_memory"
    assert service.records[0].content == "User prefers concise answers."


def test_memory_remember_without_explicit_signal_returns_pending_candidate() -> None:
    store = CurrentProcessMemoryStore()
    tool = MemoryRememberTool(
        memory_store=store,
        session_ref=SessionRef(ref_type="session", ref_id="session-memory-tool"),
    )

    result = tool.execute(
        _request(
            "memory.remember",
            {"content": "User likes terse answers.", "scope": "session"},
        )
    )

    assert result.status == "succeeded"
    assert result.safe_result["written"] is False
    assert result.safe_result["policy_status"] == "pending"
    assert store.safe_inspect() == ()


def test_memory_search_returns_safe_previews_from_store() -> None:
    store = CurrentProcessMemoryStore()
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-tool")
    store.write_record(
        MemoryRecord(
            schema_version="1",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory.concise"),
            scope="session",
            memory_kind="preference",
            session_ref=session_ref,
            conversation_ref=None,
            trace_id="trace-seed",
            turn_id="turn-seed",
            content="User prefers concise answers.",
            write_authorization="explicit_user",
            created_at=datetime.now(UTC),
            tags=("preference",),
        )
    )

    result = MemorySearchTool(memory_store=store, session_ref=session_ref).execute(
        _request("memory.search", {"query": "concise", "scope": "session"})
    )

    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "memory_search"
    assert result.safe_result["result_count"] == 1
    first = result.safe_result["results"][0]
    assert first["memory_ref"] == "memory.concise"
    assert "concise answers" in first["content_preview"]
    assert first["raw_transcript_persisted"] is False


def test_memory_list_recent_returns_bounded_safe_rows() -> None:
    store = CurrentProcessMemoryStore()
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-tool")
    store.write_record(
        MemoryRecord(
            schema_version="1",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory.one"),
            scope="session",
            memory_kind="fact",
            session_ref=session_ref,
            conversation_ref=None,
            trace_id="trace-seed",
            turn_id="turn-seed",
            content="User is building Marvex memory tools.",
            write_authorization="explicit_user",
            created_at=datetime.now(UTC),
        )
    )

    result = MemoryListRecentTool(memory_store=store, session_ref=session_ref).execute(
        _request("memory.list_recent", {"scope": "session", "max_results": 5})
    )

    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "memory_list_recent"
    assert result.safe_result["result_count"] == 1


def test_memory_forget_exact_ref_removes_record() -> None:
    store = CurrentProcessMemoryStore()
    session_ref = SessionRef(ref_type="session", ref_id="session-memory-tool")
    store.write_record(
        MemoryRecord(
            schema_version="1",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory.remove"),
            scope="session",
            memory_kind="fact",
            session_ref=session_ref,
            conversation_ref=None,
            trace_id="trace-seed",
            turn_id="turn-seed",
            content="User wants this temporary memory removed.",
            write_authorization="explicit_user",
            created_at=datetime.now(UTC),
        )
    )

    result = MemoryForgetTool(memory_store=store, session_ref=session_ref).execute(
        _request("memory.forget", {"memory_ref": "memory.remove"})
    )

    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "memory_forget"
    assert result.safe_result["forgotten"] is True
    assert store.read_by_session(session_ref).record_count == 0
