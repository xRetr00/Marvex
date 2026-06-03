from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts import TraceLevel, TraceStage
from packages.control_plane_api.logs import logs_payload
from packages.telemetry import InMemoryTraceReader, make_trace_event


def test_logs_payload_projects_low_level_tool_debug_fields() -> None:
    trace_reader = InMemoryTraceReader()
    trace_reader.emit(
        make_trace_event(
            schema_version="1",
            trace_id="trace-tool-log",
            turn_id="turn-tool-log",
            stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
            level=TraceLevel.DEBUG,
            message="Tool calls received.",
            data={
                "turn_id": "turn-tool-log",
                "tool_status": "tool_call_results",
                "tool_boundary": "agentic_tool_loop",
                "tool_loop_step": 1,
                "tool_result_count": 2,
                "tool_result_statuses": ["succeeded", "error"],
                "tool_result_reason_codes": ["", "invalid_arguments"],
            },
            timestamp=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        )
    )

    payload = logs_payload(None, trace_reader=trace_reader)

    tools_log = next(item for item in payload["logs"] if item["name"] == "tools.trace.log")
    text = "\n".join(tools_log["lines"])
    assert "tool_status=tool_call_results" in text
    assert "tool_boundary=agentic_tool_loop" in text
    assert "tool_loop_step=1" in text
    assert "tool_result_count=2" in text
    assert "tool_result_statuses=succeeded,error" in text
