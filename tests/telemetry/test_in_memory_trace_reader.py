from datetime import UTC, datetime
from pathlib import Path

from packages.contracts import TraceLevel, TraceStage
from packages.telemetry import make_trace_event


def make_event(**data):
    return make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-reader-test",
        turn_id="turn-reader-test",
        stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
        level=TraceLevel.INFO,
        message="Provider response received.",
        data=data,
        timestamp=datetime(2026, 5, 15, 9, 30, tzinfo=UTC),
    )


def test_in_memory_trace_reader_records_current_process_events_by_trace_id():
    from packages.telemetry import InMemoryTraceReader

    reader = InMemoryTraceReader()
    reader.emit(make_event(status="completed", usage={"total_count": 3}))

    envelope = reader.read_trace("trace-reader-test")

    assert envelope == {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-reader-test",
        "scope": "current_process",
        "source": "in_memory",
        "events": [
            {
                "trace_id": "trace-reader-test",
                "turn_id": "turn-reader-test",
                "event_id": "turn-reader-test:provider_response_received",
                "timestamp": "2026-05-15T09:30:00Z",
                "stage": "provider_response_received",
                "level": "info",
                "message": "Provider response received.",
                "status": "completed",
                "usage": {"total_count": 3},
            }
        ],
        "event_count": 1,
        "truncated": False,
    }


def test_in_memory_trace_reader_returns_none_for_unknown_trace_id():
    from packages.telemetry import InMemoryTraceReader

    reader = InMemoryTraceReader()
    reader.emit(make_event())

    assert reader.read_trace("trace-missing") is None


def test_in_memory_trace_reader_projection_excludes_raw_and_sensitive_data():
    from packages.telemetry import InMemoryTraceReader

    reader = InMemoryTraceReader(max_message_length=24)
    reader.emit(
        make_event(
            prompt="raw user prompt",
            messages=[{"role": "user", "content": "raw message"}],
            raw_provider_output="raw provider payload",
            raw_preview="raw preview",
            parsed_payload={"text": "parsed"},
            traceback="stack trace secret",
            api_key="secret-key",
            environment={"PATH": "secret"},
            file_contents="secret file",
            provider_response_id="provider-response-secret",
            status="completed",
            finish_reason="stop",
            service_name="local-api",
        )
    )

    envelope = reader.read_trace("trace-reader-test")

    event = envelope["events"][0]
    serialized = str(envelope).lower()
    assert "data" not in event
    assert "schema_version" not in event
    assert "prompt" not in serialized
    assert "raw user prompt" not in serialized
    assert "messages" not in serialized
    assert "raw provider payload" not in serialized
    assert "raw preview" not in serialized
    assert "parsed" not in serialized
    assert "stack trace secret" not in serialized
    assert "secret-key" not in serialized
    assert "environment" not in serialized
    assert "secret file" not in serialized
    assert "provider_response_id" not in serialized
    assert "provider-response-secret" not in serialized
    assert event["status"] == "completed"
    assert event["finish_reason"] == "stop"
    assert event["service_name"] == "local-api"


def test_in_memory_trace_reader_projects_safe_session_conversation_refs():
    from packages.telemetry import InMemoryTraceReader

    reader = InMemoryTraceReader()
    reader.emit(
        make_event(
            session_ref={"ref_type": "session", "ref_id": "session-reader-001"},
            conversation_ref={
                "ref_type": "conversation",
                "ref_id": "conversation-reader-001",
            },
            prompt="raw prompt must not project",
            transcript="full transcript must not project",
        )
    )

    envelope = reader.read_trace("trace-reader-test")

    event = envelope["events"][0]
    serialized = str(envelope).lower()
    assert event["session_ref"] == {
        "ref_type": "session",
        "ref_id": "session-reader-001",
    }
    assert event["conversation_ref"] == {
        "ref_type": "conversation",
        "ref_id": "conversation-reader-001",
    }
    assert "raw prompt" not in serialized
    assert "full transcript" not in serialized


def test_in_memory_trace_reader_projects_low_level_tool_debug_fields():
    from packages.telemetry import InMemoryTraceReader

    reader = InMemoryTraceReader()
    reader.emit(
        make_event(
            tool_status="provider_tool_calls_received",
            tool_boundary="provider_worker_process",
            tool_call_count=2,
            tool_call_names=["builtin.browser_use", "file.write"],
            tool_call_ids=["call-browser", "call-file"],
            tool_argument_keys=["builtin.browser_use.task", "file.write.path"],
            tool_argument_value_lengths=["builtin.browser_use.task:18", "file.write.path:12"],
            raw_tool_payload={"arguments": "must not project"},
        )
    )

    envelope = reader.read_trace("trace-reader-test")

    event = envelope["events"][0]
    serialized = str(envelope).lower()
    assert event["tool_status"] == "provider_tool_calls_received"
    assert event["tool_boundary"] == "provider_worker_process"
    assert event["tool_call_count"] == 2
    assert event["tool_call_names"] == ["builtin.browser_use", "file.write"]
    assert event["tool_argument_keys"] == ["builtin.browser_use.task", "file.write.path"]
    assert "raw_tool_payload" not in serialized
    assert "must not project" not in serialized


def test_in_memory_trace_reader_is_instance_owned_not_module_global():
    from packages.telemetry import InMemoryTraceReader

    first_reader = InMemoryTraceReader()
    second_reader = InMemoryTraceReader()
    first_reader.emit(make_event())

    assert first_reader.read_trace("trace-reader-test") is not None
    assert second_reader.read_trace("trace-reader-test") is None

    source = (Path("packages") / "telemetry" / "trace_reader.py").read_text(
        encoding="utf-8"
    )
    assert "GLOBAL" not in source
    assert "InMemoryTraceReader()" not in source


def test_in_memory_trace_reader_lists_recent_trace_ids_without_exposing_events():
    from packages.telemetry import InMemoryTraceReader

    reader = InMemoryTraceReader()
    for index in range(4):
        reader.emit(
            make_trace_event(
                schema_version="0.1.1-draft",
                trace_id=f"trace-reader-{index}",
                turn_id=f"turn-reader-{index}",
                stage=TraceStage.TURN_COMPLETED,
                level=TraceLevel.INFO,
                message="Turn completed.",
                data={"status": "completed"},
                timestamp=datetime(2026, 5, 15, 9, 30, tzinfo=UTC),
            )
        )

    assert reader.trace_ids(limit=2) == ("trace-reader-2", "trace-reader-3")
