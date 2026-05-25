from packages.contracts import ConversationRef, SessionRef
from packages.session_runtime import (
    BackendSessionCoordinator,
    CurrentProcessSessionRegistry,
    TurnLinkageMetadata,
)


def make_linkage(index: int) -> TurnLinkageMetadata:
    return TurnLinkageMetadata(
        schema_version="0.1.1-draft",
        trace_id=f"trace-session-{index}",
        turn_id=f"turn-session-{index}",
        session_ref=SessionRef(ref_type="session", ref_id="session-001"),
        conversation_ref=ConversationRef(
            ref_type="conversation",
            ref_id="conversation-001",
        ),
        previous_response_id_present=index > 1,
        transcript_persisted=False,
    )


def test_registry_groups_turns_by_session_without_transcripts_or_provider_ids():
    registry = CurrentProcessSessionRegistry()
    registry.record_turn(make_linkage(1))
    registry.record_turn(make_linkage(2))

    projection = registry.read_session_projection(
        SessionRef(ref_type="session", ref_id="session-001")
    )

    assert projection is not None
    assert projection.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "scope": "current_process",
        "session_ref": {"ref_type": "session", "ref_id": "session-001"},
        "conversation_refs": [
            {"ref_type": "conversation", "ref_id": "conversation-001"}
        ],
        "turn_count": 2,
        "turn_ids": ["turn-session-1", "turn-session-2"],
        "trace_ids": ["trace-session-1", "trace-session-2"],
        "previous_response_id_seen": True,
        "transcript_persisted": False,
    }
    serialized = repr(projection.safe_projection()).lower()
    assert "raw prompt" not in serialized
    assert "provider payload" not in serialized
    assert "previous-response" not in serialized


def test_registry_groups_turns_by_conversation_without_owning_session_lifecycle():
    registry = CurrentProcessSessionRegistry()
    registry.record_turn(make_linkage(1))

    projection = registry.read_conversation_projection(
        ConversationRef(ref_type="conversation", ref_id="conversation-001")
    )

    assert projection is not None
    assert projection.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "scope": "current_process",
        "conversation_ref": {
            "ref_type": "conversation",
            "ref_id": "conversation-001",
        },
        "session_refs": [{"ref_type": "session", "ref_id": "session-001"}],
        "turn_count": 1,
        "turn_ids": ["turn-session-1"],
        "trace_ids": ["trace-session-1"],
        "previous_response_id_seen": False,
        "transcript_persisted": False,
    }


def test_registry_is_instance_owned_and_current_process_only():
    first = CurrentProcessSessionRegistry()
    second = CurrentProcessSessionRegistry()
    first.record_turn(make_linkage(1))

    session_ref = SessionRef(ref_type="session", ref_id="session-001")

    assert first.read_session_projection(session_ref) is not None
    assert second.read_session_projection(session_ref) is None


def test_backend_session_coordinator_mints_safe_handles_without_transcripts_or_tokens():
    coordinator = BackendSessionCoordinator(clock=lambda: 1770000000000)

    handle = coordinator.create_session(title="Planning")

    projection = handle.safe_projection()
    assert projection["session_ref"]["ref_type"] == "session"
    assert projection["title"] == "Planning"
    assert projection["turn_count"] == 0
    assert projection["trace_count"] == 0
    assert projection["transcript_persisted"] is False
    serialized = repr(projection).lower()
    assert "token" not in serialized
    assert "bearer" not in serialized
    assert "raw prompt" not in serialized


def test_backend_session_coordinator_auto_registers_manual_session_refs():
    coordinator = BackendSessionCoordinator(clock=lambda: 1770000000000)
    linkage = make_linkage(1)

    coordinator.record_turn(linkage)

    sessions = coordinator.list_sessions()
    assert len(sessions) == 1
    projection = sessions[0].safe_projection()
    assert projection["session_ref"] == {"ref_type": "session", "ref_id": "session-001"}
    assert projection["title"] == "Session session-001"
    assert projection["turn_count"] == 1
    assert projection["trace_count"] == 1
    assert projection["transcript_persisted"] is False
