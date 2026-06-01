from packages.session_runtime import SessionContextStore


def test_session_context_store_keeps_bounded_last_turn_projection_without_raw_transcript() -> None:
    store = SessionContextStore(max_items_per_session=2)

    store.record_user_turn("s1", trace_id="trace-1", turn_id="turn-1", text="First raw user message that should be summarized.")
    store.record_assistant_turn("s1", trace_id="trace-2", turn_id="turn-2", text="Assistant created output.txt.", tool_result_refs=("tool.file.write",), entity_refs=("Desktop/output.txt",))
    store.record_user_turn("s1", trace_id="trace-3", turn_id="turn-3", text="Now write in that file.")

    projection = store.safe_projection("s1")

    assert projection["item_count"] == 2
    assert projection["transcript_persisted"] is False
    assert [item["turn_id"] for item in projection["items"]] == ["turn-2", "turn-3"]
    assert projection["items"][0]["tool_result_refs"] == ["tool.file.write"]
    assert projection["items"][0]["entity_refs"] == ["Desktop/output.txt"]
    assert "First raw user message" not in str(projection)


def test_session_context_summary_is_safe_prompt_context() -> None:
    store = SessionContextStore(max_items_per_session=4)
    store.record_user_turn("s1", trace_id="trace-1", turn_id="turn-1", text="Please remember this: User prefers concise answers.")
    store.record_assistant_turn("s1", trace_id="trace-2", turn_id="turn-2", text="Saved that preference to memory.", memory_refs=("memory.concise",))

    context = store.prompt_context("s1")

    assert "Recent session context:" in context
    assert "turn-1" in context
    assert "memory.concise" in context
    assert "raw transcript" not in context.lower()


def test_session_context_store_round_trips_safe_snapshot() -> None:
    store = SessionContextStore(max_items_per_session=4)
    store.record_user_turn("s1", trace_id="trace-1", turn_id="turn-1", text="Remember this: I prefer short answers.")
    store.record_assistant_turn("s1", trace_id="trace-2", turn_id="turn-2", text="Saved.", memory_refs=("memory.short",))

    restored = SessionContextStore.from_snapshot(store.safe_snapshot(), max_items_per_session=4)

    projection = restored.safe_projection("s1")
    assert projection["item_count"] == 2
    assert projection["items"][1]["memory_refs"] == ["memory.short"]
    assert projection["transcript_persisted"] is False
