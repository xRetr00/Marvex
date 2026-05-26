import json
from datetime import UTC, datetime

import pytest

from packages.contracts import TraceLevel, TraceStage
from packages.telemetry import make_trace_event


def make_event(trace_id: str = "trace-persist-test", **data):
    return make_trace_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id="turn-persist-test",
        stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
        level=TraceLevel.INFO,
        message="Provider response received.",
        data=data,
        timestamp=datetime(2026, 5, 16, 9, 30, tzinfo=UTC),
    )


def test_persistent_trace_store_writes_redacted_ndjson_and_reads_safe_envelope(tmp_path):
    from packages.telemetry import PersistentTraceStore

    trace_file = tmp_path / "telemetry" / "traces.ndjson"
    store = PersistentTraceStore(trace_file_path=trace_file, local_user_root=tmp_path)

    store.emit(
        make_event(
            status="completed",
            raw_provider_output="raw provider payload",
            prompt="raw prompt text",
            provider_response_id="provider-response-secret",
            api_key="secret-token",
            usage={"total_count": 4},
        )
    )

    raw_text = trace_file.read_text(encoding="utf-8")
    assert raw_text.count("\n") == 1
    assert "raw provider payload" not in raw_text
    assert "raw prompt text" not in raw_text
    assert "provider-response-secret" not in raw_text
    assert "secret-token" not in raw_text
    assert "[REDACTED]" in raw_text

    envelope = store.read_trace("trace-persist-test")

    assert envelope == {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-persist-test",
        "scope": "local_persistence",
        "source": "local_file",
        "events": [
            {
                "trace_id": "trace-persist-test",
                "turn_id": "turn-persist-test",
                "event_id": "turn-persist-test:provider_response_received",
                "timestamp": "2026-05-16T09:30:00Z",
                "stage": "provider_response_received",
                "level": "info",
                "message": "Provider response received.",
                "status": "completed",
                "usage": {"total_count": 4},
            }
        ],
        "event_count": 1,
        "truncated": False,
        "malformed_record_count": 0,
    }


def test_persistent_trace_store_projects_safe_session_conversation_refs(tmp_path):
    from packages.telemetry import PersistentTraceStore

    trace_file = tmp_path / "telemetry" / "traces.ndjson"
    store = PersistentTraceStore(trace_file_path=trace_file, local_user_root=tmp_path)

    store.emit(
        make_event(
            session_ref={"ref_type": "session", "ref_id": "session-persist-001"},
            conversation_ref={
                "ref_type": "conversation",
                "ref_id": "conversation-persist-001",
            },
            prompt="raw prompt text",
            transcript="full transcript body",
        )
    )

    raw_text = trace_file.read_text(encoding="utf-8")
    envelope = store.read_trace("trace-persist-test")
    event = envelope["events"][0]

    assert event["session_ref"] == {
        "ref_type": "session",
        "ref_id": "session-persist-001",
    }
    assert event["conversation_ref"] == {
        "ref_type": "conversation",
        "ref_id": "conversation-persist-001",
    }
    assert "raw prompt text" not in raw_text
    assert "full transcript body" not in raw_text
    assert "raw prompt text" not in str(envelope)
    assert "full transcript body" not in str(envelope)


def test_persistent_trace_store_rejects_paths_outside_local_user_root(tmp_path):
    from packages.telemetry import PersistentTraceStore

    with pytest.raises(ValueError, match="local-user scoped"):
        PersistentTraceStore(
            trace_file_path=tmp_path.parent / "traces.ndjson",
            local_user_root=tmp_path,
        )


def test_persistent_trace_store_rejects_non_json_compatible_event_data(tmp_path):
    from packages.telemetry import PersistentTraceStore

    store = PersistentTraceStore(
        trace_file_path=tmp_path / "telemetry" / "traces.ndjson",
        local_user_root=tmp_path,
    )
    event = make_event(bad=object())

    with pytest.raises(ValueError, match="JSON-compatible"):
        store.emit(event)

    assert not (tmp_path / "telemetry" / "traces.ndjson").exists()


def test_persistent_trace_store_ignores_malformed_records_when_reading(tmp_path):
    from packages.telemetry import PersistentTraceStore

    trace_file = tmp_path / "telemetry" / "traces.ndjson"
    trace_file.parent.mkdir(parents=True)
    trace_file.write_text(
        "not-json\n" + json.dumps(make_event().model_dump(mode="json")) + "\n",
        encoding="utf-8",
    )
    store = PersistentTraceStore(trace_file_path=trace_file, local_user_root=tmp_path)

    envelope = store.read_trace("trace-persist-test")

    assert envelope["event_count"] == 1
    assert envelope["malformed_record_count"] == 1
    assert envelope["events"][0]["trace_id"] == "trace-persist-test"


def test_persistent_trace_store_rotates_bounded_local_files_without_secret_leaks(tmp_path):
    from packages.telemetry import PersistentTraceStore

    trace_file = tmp_path / "telemetry" / "traces.ndjson"
    store = PersistentTraceStore(
        trace_file_path=trace_file,
        local_user_root=tmp_path,
        max_file_bytes=1,
        max_rotated_files=2,
    )

    for index in range(4):
        store.emit(make_event(trace_id=f"trace-{index}", token="secret-token"))

    files = sorted(trace_file.parent.glob("traces.ndjson*"))
    assert [path.name for path in files] == [
        "traces.ndjson",
        "traces.ndjson.1",
        "traces.ndjson.2",
    ]
    for path in files:
        assert "secret-token" not in path.read_text(encoding="utf-8")


def test_persistent_trace_store_write_failure_uses_safe_error(tmp_path):
    from packages.telemetry import PersistentTraceStore, TelemetryPersistenceError

    store = PersistentTraceStore(trace_file_path=tmp_path, local_user_root=tmp_path)

    with pytest.raises(TelemetryPersistenceError) as exc_info:
        store.emit(make_event(token="secret-token"))

    error = exc_info.value
    assert error.error_code == "TELEMETRY_WRITE_FAILED"
    assert "secret-token" not in str(error)


def test_persistent_trace_store_lists_recent_trace_ids_from_local_files(tmp_path):
    from packages.telemetry import PersistentTraceStore

    trace_file = tmp_path / "telemetry" / "traces.ndjson"
    store = PersistentTraceStore(trace_file_path=trace_file, local_user_root=tmp_path)

    for index in range(4):
        store.emit(make_event(trace_id=f"trace-persist-{index}", token="secret-token"))

    assert store.trace_ids(limit=2) == ("trace-persist-2", "trace-persist-3")
