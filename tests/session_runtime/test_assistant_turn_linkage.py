from packages.contracts import (
    AssistantMode,
    AssistantTurnInput,
    ConversationRef,
    PolicyContext,
    Sensitivity,
    SessionRef,
)


def test_build_turn_linkage_from_assistant_turn_input_is_reference_only():
    from packages.session_runtime import build_turn_linkage_from_assistant_turn_input

    turn_input = AssistantTurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-linkage-test",
        turn_id="turn-linkage-test",
        input_event_id="event-linkage-test",
        session_ref=SessionRef(ref_type="session", ref_id="session-linkage-001"),
        identity_ref=None,
        user_visible_input="raw user text must stay out of linkage",
        assistant_mode=AssistantMode.DEFAULT,
        policy_context=PolicyContext(
            requested_capabilities=[],
            sensitivity=Sensitivity.NORMAL,
        ),
        metadata={"prompt": "raw prompt must stay out"},
    )

    linkage = build_turn_linkage_from_assistant_turn_input(
        turn_input,
        conversation_ref=ConversationRef(
            ref_type="conversation",
            ref_id="conversation-linkage-001",
        ),
        previous_response_id="previous-response-secret",
    )

    assert linkage.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-linkage-test",
        "turn_id": "turn-linkage-test",
        "session_ref": {"ref_type": "session", "ref_id": "session-linkage-001"},
        "conversation_ref": {
            "ref_type": "conversation",
            "ref_id": "conversation-linkage-001",
        },
        "previous_response_id_present": True,
        "transcript_persisted": False,
    }
    serialized = repr(linkage).lower()
    assert "raw user text" not in serialized
    assert "raw prompt" not in serialized
    assert "previous-response-secret" not in serialized

