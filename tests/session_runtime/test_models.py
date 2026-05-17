from pydantic import ValidationError

from packages.contracts import ConversationRef, SessionRef


def test_session_and_conversation_refs_accept_safe_ids_only():
    session_ref = SessionRef(ref_type="session", ref_id="session-001")
    conversation_ref = ConversationRef(
        ref_type="conversation",
        ref_id="conversation-001",
    )

    assert session_ref.ref_id == "session-001"
    assert conversation_ref.ref_id == "conversation-001"

    unsafe_values = [" session-001", "session/001", "", "conversation 001"]
    for value in unsafe_values:
        try:
            SessionRef(ref_type="session", ref_id=value)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"SessionRef accepted unsafe id {value!r}")

    for value in unsafe_values:
        try:
            ConversationRef(ref_type="conversation", ref_id=value)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"ConversationRef accepted unsafe id {value!r}")


def test_turn_linkage_projection_is_reference_only_and_previous_response_safe():
    from packages.session_runtime import TurnLinkageMetadata

    linkage = TurnLinkageMetadata(
        schema_version="0.1.1-draft",
        trace_id="trace-session-test",
        turn_id="turn-session-test",
        session_ref=SessionRef(ref_type="session", ref_id="session-001"),
        conversation_ref=ConversationRef(
            ref_type="conversation",
            ref_id="conversation-001",
        ),
        previous_response_id_present=True,
        transcript_persisted=False,
    )

    assert linkage.safe_projection() == {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-session-test",
        "turn_id": "turn-session-test",
        "session_ref": {"ref_type": "session", "ref_id": "session-001"},
        "conversation_ref": {
            "ref_type": "conversation",
            "ref_id": "conversation-001",
        },
        "previous_response_id_present": True,
        "transcript_persisted": False,
    }
    assert "previous-response" not in repr(linkage)
    assert "raw prompt" not in repr(linkage.safe_projection())


def test_turn_linkage_rejects_transcript_persistence_by_default():
    from packages.session_runtime import TurnLinkageMetadata

    try:
        TurnLinkageMetadata(
            schema_version="0.1.1-draft",
            trace_id="trace-session-test",
            turn_id="turn-session-test",
            session_ref=None,
            conversation_ref=None,
            previous_response_id_present=False,
            transcript_persisted=True,
        )
    except ValidationError as exc:
        assert "transcript_persisted" in str(exc)
    else:
        raise AssertionError("TurnLinkageMetadata accepted transcript persistence")

