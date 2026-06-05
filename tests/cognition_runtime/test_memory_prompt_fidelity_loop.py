from __future__ import annotations

from datetime import UTC, datetime

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import MemoryRecord, MemoryRef, SQLiteMemoryStore


def _turn_input(text: str, *, turn_id: str = "turn-memory-fidelity"):
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-memory-fidelity",
        event_id=f"{turn_id}:input",
        text=text,
        timestamp=datetime(2026, 5, 21, 9, 0, tzinfo=UTC),
        session_id="session-memory-fidelity",
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-memory-fidelity",
        turn_id=turn_id,
        input_event=event,
    )


def _seed_record(store: SQLiteMemoryStore, *, content: str) -> None:
    store.write_record(
        MemoryRecord(
            schema_version="0.1.1-draft",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory-fidelity-001"),
            scope="session",
            memory_kind="fact",
            session_ref=SessionRef(ref_type="session", ref_id="session-memory-fidelity"),
            conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-memory-fidelity"),
            trace_id="trace-seeded-memory",
            turn_id="turn-seeded-memory",
            content=content,
            write_authorization="policy_approved",
            created_at=datetime(2026, 5, 21, 8, 55, tzinfo=UTC),
            tags=("profile",),
            raw_transcript_persisted=False,
        )
    )


def test_cognition_adaptive_prompt_carries_real_question_and_recalled_memory(tmp_path) -> None:
    from packages.cognition_runtime import CognitionRuntime

    store = SQLiteMemoryStore(memory_db_path=tmp_path / "memory.sqlite", local_user_root=tmp_path)
    _seed_record(store, content="User preferred project codename is Cedar.")

    result = CognitionRuntime(memory_store=store).assemble_turn(
        _turn_input("What project codename do I prefer?")
    )

    sections = tuple(section.safe_content for section in result.prompt_result.plan.sections if section.included)
    joined = "\n".join(sections)

    assert "What project codename do I prefer?" in joined
    assert "User preferred project codename is Cedar." in joined
    assert "Approved memory ref is available." not in joined
    assert "User requested a simple assistant response." not in joined
    assert result.prompt_result.plan.route_profile.total_context_budget == 6000
    assert result.context_pack.budget.max_context_tokens == 6000
    assert "system_policy" in result.prompt_projection.section_kinds
    assert result.raw_prompt_persisted is False


def test_local_memory_loop_policy_write_recall_restart_and_belief_revision(tmp_path) -> None:
    from packages.cognition_runtime import LocalMemoryLoop

    loop = LocalMemoryLoop.open(vault_root=tmp_path / "vault")
    turn_one = _turn_input(
        "Remember that my preferred project codename is Cedar.",
        turn_id="turn-memory-write-1",
    )

    write_one = loop.write_from_turn(turn_one)
    recall_one = loop.recall_for_turn(
        _turn_input("What project codename do I prefer?", turn_id="turn-memory-read-2")
    )

    assert write_one.written is True
    assert write_one.policy_audit.decision == "allow"
    assert write_one.record is not None
    assert write_one.record.write_authorization == "policy_approved"
    assert recall_one.records[0].content == "User preferred project codename is Cedar."
    assert recall_one.evidence_refs[0].source == "memory_loop"

    restarted = LocalMemoryLoop.open(vault_root=tmp_path / "vault")
    restart_recall = restarted.recall_for_turn(
        _turn_input("What project codename do I prefer?", turn_id="turn-memory-read-3")
    )
    assert restart_recall.records[0].content == "User preferred project codename is Cedar."

    turn_three = _turn_input(
        "Actually, my preferred project codename is Amber.",
        turn_id="turn-memory-write-3",
    )
    write_two = restarted.write_from_turn(turn_three)
    final_recall = restarted.recall_for_turn(
        _turn_input("What project codename do I prefer now?", turn_id="turn-memory-read-4")
    )

    assert write_two.revised_memory_ref == write_one.record.memory_ref.ref_id
    assert [record.content for record in final_recall.records] == [
        "User preferred project codename is Amber."
    ]
    markdown_files = sorted((tmp_path / "vault" / "wiki" / "summaries").glob("*.md"))
    assert markdown_files
    sample = markdown_files[0].read_text(encoding="utf-8")
    assert "source_id: memory_loop" in sample
    assert "[[Project Codename]]" in sample
    assert "User preferred project codename is Amber." in sample
    assert "raw_secret_persisted: false" in sample
    assert "raw prompt" not in sample.lower()
    assert "transcript" not in sample.lower()


def test_local_memory_loop_writes_explicit_remember_keywords(tmp_path) -> None:
    from packages.cognition_runtime import LocalMemoryLoop

    loop = LocalMemoryLoop.open(vault_root=tmp_path / "vault")

    write = loop.write_from_turn(
        _turn_input("Remember this: User prefers concise answers.", turn_id="turn-explicit-memory")
    )
    recall = loop.recall_for_turn(
        _turn_input("What answer style do I prefer?", turn_id="turn-explicit-recall")
    )

    assert write.written is True
    assert write.policy_audit.capability == "memory_explicit_write"
    assert write.record is not None
    assert write.record.memory_kind == "fact"
    assert write.record.write_authorization == "explicit_user"
    assert recall.records[0].content == "User prefers concise answers."
