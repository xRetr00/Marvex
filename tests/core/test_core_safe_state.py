from packages.session_runtime import ConversationEntityStore, ENTITY_FILE, SessionContextStore


def test_core_safe_state_helpers_round_trip_session_and_entity_snapshots(tmp_path, monkeypatch):
    from services.core.safe_state import (
        automation_pending_state_path,
        conversation_entity_state_path,
        load_pending_automation_state,
        load_json_state,
        save_json_state,
        save_pending_automation_state,
        session_context_state_path,
    )

    monkeypatch.setenv("MARVEX_SESSION_CONTEXT_STATE", str(tmp_path / "session_context.json"))
    monkeypatch.setenv("MARVEX_CONVERSATION_ENTITY_STATE", str(tmp_path / "conversation_entities.json"))
    monkeypatch.setenv("MARVEX_PENDING_AUTOMATION_STATE", str(tmp_path / "pending_automation.json"))

    session_store = SessionContextStore()
    session_store.record_user_turn("s1", trace_id="trace-1", turn_id="turn-1", text="remember this")
    save_json_state(session_context_state_path(), session_store.safe_snapshot())

    restored_session = SessionContextStore.from_snapshot(load_json_state(session_context_state_path()))
    assert restored_session.safe_projection("s1")["item_count"] == 1

    entity_store = ConversationEntityStore()
    entity_store.remember("s1", entity_type=ENTITY_FILE, ref_id="Desktop/a.txt", label="a.txt", turn_id="turn-2")
    save_json_state(conversation_entity_state_path(), entity_store.safe_snapshot())

    restored_entity = ConversationEntityStore.from_snapshot(load_json_state(conversation_entity_state_path()))
    assert restored_entity.most_recent("s1", entity_type=ENTITY_FILE).ref_id == "Desktop/a.txt"

    pending = {
        "approval-turn-1": {
            "capability_id": "browser_use.task",
            "resource_type": "browser",
            "capability": "browser_click_type",
            "arguments": {"task": "open example.com", "raw_secret": "drop"},
        }
    }
    save_pending_automation_state(automation_pending_state_path(), pending)

    restored_pending = load_pending_automation_state(automation_pending_state_path())
    assert restored_pending == {
        "approval-turn-1": {
            "capability_id": "browser_use.task",
            "resource_type": "browser",
            "capability": "browser_click_type",
            "arguments": {"task": "open example.com"},
        }
    }
