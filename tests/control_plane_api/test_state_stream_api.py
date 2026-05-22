from __future__ import annotations

import io
import json
from wsgiref.util import setup_testing_defaults

from packages.contracts.state_event import AssistantStateEvent, AssistantStatusKind
from packages.control_plane_api import (
    ControlPlaneSnapshot,
    InMemoryApprovalStore,
    create_control_plane_api_app,
)
from packages.state_bus import AssistantStateBus, reset_default_bus


def _make_app(state_bus=None):
    reset_default_bus()
    store = InMemoryApprovalStore()
    snapshot = ControlPlaneSnapshot.foundation_default(schema_version="1")
    return create_control_plane_api_app(
        approval_store=store,
        snapshot=snapshot,
        local_auth_token="test-state-token",
        state_bus=state_bus,
    )


def _call(app, path: str, *, method: str = "GET", token: str | None = "test-state-token"):
    environ: dict = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    environ["wsgi.input"] = io.BytesIO(b"")
    environ["CONTENT_LENGTH"] = "0"
    captured: dict = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured.get("headers", {}), response


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
    """Drive the WSGI app with a fake environ and assert SSE framing."""
    bus = AssistantStateBus()
    bus.publish_status(AssistantStatusKind.WORKING, detail="sse_test")

    app = _make_app(state_bus=bus)

    environ: dict = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = "/control/state/stream"
    environ["HTTP_AUTHORIZATION"] = "Bearer test-state-token"
    environ["wsgi.input"] = io.BytesIO(b"")
    environ["CONTENT_LENGTH"] = "0"

    captured: dict = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    # Collect only the first chunk — the snapshot frame
    gen = app(environ, start_response)
    first_chunk = next(iter(gen))

    assert captured["status"] == "200 OK"
    assert captured["headers"].get("Content-Type") == "text/event-stream"

    # The first frame must be a valid SSE data line
    text = first_chunk.decode("utf-8")
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

    environ: dict = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = "/control/state/stream"
    environ["wsgi.input"] = io.BytesIO(b"")
    environ["CONTENT_LENGTH"] = "0"
    # No Authorization header

    captured: dict = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status

    b"".join(app(environ, start_response))
    assert captured["status"] == "401 Unauthorized"


def test_state_stream_emits_all_required_fields() -> None:
    bus = AssistantStateBus()
    bus.publish_status(
        AssistantStatusKind.LISTENING,
        audio_level=0.6,
        trace_id="trace-sse",
        session_ref="sess-1",
    )
    app = _make_app(state_bus=bus)

    environ: dict = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = "/control/state/stream"
    environ["HTTP_AUTHORIZATION"] = "Bearer test-state-token"
    environ["wsgi.input"] = io.BytesIO(b"")
    environ["CONTENT_LENGTH"] = "0"

    captured: dict = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status

    gen = app(environ, start_response)
    first_chunk = next(iter(gen))

    text = first_chunk.decode("utf-8")
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
