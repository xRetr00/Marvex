from datetime import UTC, datetime
from pathlib import Path

from packages.contracts import TraceEvent, TraceLevel, TraceStage
from packages.telemetry import NoopTelemetrySink, TelemetrySink, make_trace_event


def test_make_trace_event_returns_valid_trace_event():
    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        stage=TraceStage.TURN_RECEIVED,
        level=TraceLevel.INFO,
        message="Turn received.",
        data={"source": "test"},
        timestamp=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
    )

    validated = TraceEvent.model_validate(event.model_dump())
    assert validated.event_id == "turn-001:turn_received"
    assert validated.trace_id == "trace-001"
    assert validated.stage == TraceStage.TURN_RECEIVED
    assert validated.data == {"source": "test"}


def test_noop_telemetry_sink_satisfies_protocol_and_stores_nothing():
    sink = NoopTelemetrySink()
    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        stage=TraceStage.TURN_COMPLETED,
        level=TraceLevel.INFO,
        message="Turn completed.",
    )

    assert isinstance(sink, TelemetrySink)
    assert sink.emit(event) is None
    assert not hasattr(sink, "events")


def test_telemetry_source_has_no_io_logging_network_or_future_module_tokens():
    source = (Path("packages") / "telemetry" / "sinks.py").read_text(
        encoding="utf-8"
    )
    lowered = source.lower()
    forbidden = [
        "logging",
        "open(",
        "path(",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "packages.adapters",
        "lmstudio",
        "cli",
        "tool",
        "memory",
        "intent",
        "voice",
        "desktop",
    ]

    assert [token for token in forbidden if token in lowered] == []
