from __future__ import annotations

import json

from packages.contracts.state_event import AssistantStateEvent, AssistantStatusKind
from packages.control_plane_api.asgi_app import iter_state_sse_frames
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from packages.state_bus import AssistantStateBus, reset_default_bus
from tests.control_plane_api.asgi_helpers import asgi_call, create_control_plane_test_app


def _make_app(state_bus=None):
    reset_default_bus()
    store = InMemoryApprovalStore()
    snapshot = ControlPlaneSnapshot.foundation_default(schema_version="1")
    return create_control_plane_test_app(
        approval_store=store,
        snapshot=snapshot,
        local_auth_token="test-state-token",
        state_bus=state_bus,
    )


def _call(app, path: str, *, method: str = "GET", token: str | None = "test-state-token"):
    status, headers, payload = asgi_call(app, path, method=method, token=token)
    return status, headers, json.dumps(payload)


def test_state_snapshot_without_bus_returns_idle() -> None:
    app = _make_app(state_bus=None)
    status, headers, body = _call(app, "/control/state")
    assert status == "200 OK"
    payload = json.loads(body)
    assert payload["status"] == "idle"
    assert payload["raw_audio_persisted"] is False
    assert 0.0 <= payload["audio_level"] <= 1.0


def test_state_snapshot_with_bus_returns_current_status() -> None:
    bus = AssistantStateBus()
    bus.publish_status(AssistantStatusKind.THINKING, detail="planning", trace_id="trace-1")
    app = _make_app(state_bus=bus)
    status, headers, body = _call(app, "/control/state")
    assert status == "200 OK"
    payload = json.loads(body)
    assert payload["status"] == "thinking"
    assert payload["detail"] == "planning"
    assert payload["raw_audio_persisted"] is False


def test_state_snapshot_requires_bearer_auth() -> None:
    app = _make_app()
    status, headers, body = _call(app, "/control/state", token=None)
    assert status == "401 Unauthorized"


def test_state_snapshot_wrong_token_rejected() -> None:
    app = _make_app()
    status, headers, body = _call(app, "/control/state", token="wrong-token")
    assert status == "401 Unauthorized"


def test_state_stream_sse_framing() -> None:
    bus = AssistantStateBus()
    bus.publish_status(AssistantStatusKind.WORKING, detail="sse_test")

    async def read_first_frame() -> str:
        frames = iter_state_sse_frames(state_bus=bus, heartbeat_interval_seconds=60.0)
        try:
            return await anext(frames)
        finally:
            await frames.aclose()

    import asyncio

    first_chunk = asyncio.run(read_first_frame())

    # The first frame must be a valid SSE data line
    text = first_chunk
    assert text.startswith("data: ")
    assert text.endswith("\n\n")

    # Parse the JSON payload
    json_part = text[len("data: "):].strip()
    payload = json.loads(json_part)
    assert payload["status"] == "working"
    assert payload["raw_audio_persisted"] is False
    assert "audio_level" in payload
    assert "ts" in payload


def test_state_stream_requires_bearer_auth() -> None:
    bus = AssistantStateBus()
    app = _make_app(state_bus=bus)

    from fastapi.testclient import TestClient

    response = TestClient(app).get("/control/state/stream")
    assert response.status_code == 401


def test_state_stream_emits_all_required_fields() -> None:
    bus = AssistantStateBus()
    bus.publish_status(
        AssistantStatusKind.LISTENING,
        audio_level=0.6,
        trace_id="trace-sse",
        session_ref="sess-1",
    )
    async def read_first_frame() -> str:
        frames = iter_state_sse_frames(state_bus=bus, heartbeat_interval_seconds=60.0)
        try:
            return await anext(frames)
        finally:
            await frames.aclose()

    import asyncio

    first_chunk = asyncio.run(read_first_frame())

    text = first_chunk
    json_part = text[len("data: "):].strip()
    payload = json.loads(json_part)

    assert payload["status"] == "listening"
    assert payload["audio_level"] == 0.6
    assert payload["trace_id"] == "trace-sse"
    assert payload["session_ref"] == "sess-1"
    assert payload["raw_audio_persisted"] is False
    assert "schema_version" in payload
    assert "ts" in payload
    assert "detail" in payload
