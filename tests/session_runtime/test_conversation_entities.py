"""Tests for conversation-scoped entity memory + reference resolution (item 01)."""

from packages.session_runtime import (
    ENTITY_FILE,
    ENTITY_WEB_RESULT,
    ConversationEntityStore,
    resolve_file_reference,
    text_references_prior_file,
)


def test_remember_and_most_recent_by_type():
    store = ConversationEntityStore()
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="Desktop/a.txt", label="a.txt", turn_id="t1")
    store.remember("s1", entity_type=ENTITY_WEB_RESULT, ref_id="https://x", label="X", turn_id="t2")
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="Desktop/b.md", label="b.md", turn_id="t3")

    assert store.most_recent("s1", entity_type=ENTITY_FILE).ref_id == "Desktop/b.md"
    assert store.most_recent("s1", entity_type=ENTITY_WEB_RESULT).ref_id == "https://x"
    assert store.most_recent("s1").entity_type == ENTITY_FILE  # b.md was last overall


def test_sessions_are_isolated():
    store = ConversationEntityStore()
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="a.txt", label="a", turn_id="t1")
    assert store.most_recent("s2", entity_type=ENTITY_FILE) is None


def test_ring_is_bounded():
    store = ConversationEntityStore(max_per_session=2)
    for i in range(3):
        store.remember("s1", entity_type=ENTITY_FILE, ref_id=f"f{i}.txt", label=f"f{i}", turn_id=f"t{i}")
    refs = [e.ref_id for e in store.recent("s1")]
    assert refs == ["f2.txt", "f1.txt"]  # f0 evicted, most-recent first


def test_text_references_prior_file_detects_backreferences():
    assert text_references_prior_file("write more into that file")
    assert text_references_prior_file("append to the file")
    assert text_references_prior_file("add a line to it")
    # An explicit filename is NOT a back-reference.
    assert not text_references_prior_file("write to notes.md")
    assert not text_references_prior_file("create report.txt")
    assert not text_references_prior_file("")


def test_resolve_file_reference_returns_last_file():
    store = ConversationEntityStore()
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="Desktop/output.txt", label="output.txt", turn_id="t1")
    assert resolve_file_reference("now write the open source summary in that file", store, "s1") == "Desktop/output.txt"


def test_resolve_file_reference_none_when_no_backref():
    store = ConversationEntityStore()
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="Desktop/output.txt", label="output.txt", turn_id="t1")
    # Explicit new filename -> not a back-reference -> no resolution.
    assert resolve_file_reference("write a summary to other.md", store, "s1") is None


def test_resolve_file_reference_none_when_no_prior_file():
    store = ConversationEntityStore()
    assert resolve_file_reference("write that file again", store, "s1") is None


def test_remember_ignores_empty_ids():
    store = ConversationEntityStore()
    store.remember("", entity_type=ENTITY_FILE, ref_id="a.txt", label="a", turn_id="t")
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="", label="a", turn_id="t")
    assert store.most_recent("s1", entity_type=ENTITY_FILE) is None


def test_conversation_entity_store_round_trips_safe_snapshot():
    store = ConversationEntityStore()
    store.remember("s1", entity_type=ENTITY_FILE, ref_id="Desktop/output.txt", label="output.txt", turn_id="t1")
    store.remember("s1", entity_type=ENTITY_WEB_RESULT, ref_id="https://example.test", label="Example", turn_id="t2")

    snapshot = store.safe_snapshot()
    restored = ConversationEntityStore.from_snapshot(snapshot)

    assert restored.most_recent("s1", entity_type=ENTITY_FILE).ref_id == "Desktop/output.txt"
    assert restored.most_recent("s1", entity_type=ENTITY_WEB_RESULT).ref_id == "https://example.test"
    assert snapshot["raw_content_persisted"] is False
