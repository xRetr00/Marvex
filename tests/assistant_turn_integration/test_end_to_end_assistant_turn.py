from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.assistant_turn_integration import (
    EndToEndTurnStateStore,
    create_end_to_end_local_turn_handler,
    run_end_to_end_assistant_turn,
)
from packages.contracts import AssistantTurnResult, TraceStage
from packages.local_api import create_local_api_asgi_app
from packages.local_api.contracts import LOCAL_TURNS_EXECUTION_MODE
from tests.local_api.asgi_helpers import asgi_call
from tests.local_api.test_health_version_api import make_provider


def _turn_input(text: str = "Calculate 2+2 with the safe calculator tool"):
    event = build_text_input_event(
        schema_version="1",
        trace_id="trace-e2e-1",
        event_id="input-e2e-1",
        text=text,
        timestamp=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
        session_id="session-e2e-1",
    )
    return build_turn_input_from_event(
        schema_version="1",
        trace_id="trace-e2e-1",
        turn_id="turn-e2e-1",
        input_event=event,
    )


def _call(app, path: str, *, method: str = "GET", token: str | None = "dev-token", body: dict | None = None):
    auth = f"Bearer {token}" if token is not None else None
    return asgi_call(app, path, method=method, auth=auth, body=body)


def _turn_body():
    return {
        "schema_version": "0.1.1-draft",
        "execution_mode": LOCAL_TURNS_EXECUTION_MODE,
        "assistant_turn_input": _turn_input().model_dump(mode="json"),
        "model": "fake-model",
        "instructions": None,
        "previous_response_id": None,
        "provider_options": {},
    }


def test_end_to_end_turn_runs_intent_context_prompt_tool_provider_and_telemetry_spine() -> None:
    store = EndToEndTurnStateStore()

    integrated = run_end_to_end_assistant_turn(_turn_input(), model="fake-model", state_store=store)

    assert isinstance(integrated.assistant_result, AssistantTurnResult)
    assert integrated.assistant_result.assistant_final_response is not None
    assert integrated.intent_projection.selected_intent["intent_kind"] == "capability_tool"
    assert integrated.context_projection.included_count >= 2
    assert integrated.prompt_projection.section_count >= 3
    assert integrated.tool_state_projection["result_status"] == "succeeded"
    assert integrated.lifecycle_projection["tool_result_delivery_ready"] is True
    assert integrated.telemetry_summary["raw_prompt_persisted"] is False
    assert integrated.telemetry_summary["raw_context_persisted"] is False
    assert "2+2" not in integrated.safe_projection().model_dump_json()

    trace = store.trace_reader.read_trace("trace-e2e-1")
    assert trace is not None
    stages = {event["stage"] for event in trace["events"]}
    assert TraceStage.TURN_RECEIVED.value in stages
    assert TraceStage.TURN_COMPLETED.value in stages
    serialized_trace = json.dumps(trace).lower()
    assert "raw prompt" not in serialized_trace
    assert "provider payload" not in serialized_trace


def test_local_api_uses_injected_e2e_handler_without_owning_runtime_policy() -> None:
    store = EndToEndTurnStateStore()
    app = create_local_api_asgi_app(
        make_provider(),
        turn_handler=create_end_to_end_local_turn_handler(state_store=store),
        trace_reader=store.trace_reader,
        local_auth_token="dev-token",
    )

    status, _headers, payload = _call(app, "/v1/turns", method="POST", body=_turn_body())
    trace_status, _trace_headers, trace_payload = _call(app, "/v1/traces/trace-e2e-1")

    assert status == "200 OK"
    assert payload["assistant_final_response"]["text"] == "The calculator result is 4."
    assert payload["metadata"]["integration_summary"]["raw_payload_persisted"] is False
    assert trace_status == "200 OK"
    assert trace_payload["event_count"] >= 5
    assert "dev-token" not in json.dumps(payload)


def test_control_plane_can_observe_trace_summary_and_approval_state_safely() -> None:
    store = EndToEndTurnStateStore()
    run_end_to_end_assistant_turn(_turn_input("Click the browser checkout button"), model="fake-model", state_store=store)

    snapshot = store.control_plane_snapshot()
    approvals = store.approval_store.list_pending()

    assert approvals.pending_count == 1
    assert approvals.approvals[0].risk_level == "high"
    assert snapshot.traces[0]["trace_id"] == "trace-e2e-1"
    assert snapshot.agent_loops[0]["pending_approval_count"] == 1
    assert snapshot.raw_payload_persisted is False
    serialized = snapshot.model_dump_json().lower()
    assert "checkout button" not in serialized
    assert "password" not in serialized

    decision = store.approval_store.deny("approval-turn-e2e-1", reason="unsafe browser action")
    assert decision is not None
    assert decision.decision == "denied"
    assert decision.execution_started is False
