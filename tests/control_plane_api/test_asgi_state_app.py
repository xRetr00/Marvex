from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient

from packages.contracts.state_event import AssistantStatusKind
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore, create_control_plane_api_app
from packages.control_plane_api.browser_session import BrowserSessionManager
from packages.state_bus import AssistantStateBus


def _wsgi_fallback(environ: dict[str, Any], start_response):
    path = str(environ.get("PATH_INFO", "/"))
    body = json.dumps({"fallback_path": path}).encode("utf-8")
    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]


def test_control_plane_asgi_state_route_uses_native_state_snapshot() -> None:
    from packages.control_plane_api.asgi_app import create_control_plane_asgi_app

    bus = AssistantStateBus()
    bus.publish_status(AssistantStatusKind.THINKING, detail="native-asgi")
    app = create_control_plane_asgi_app(
        control_wsgi_app=_wsgi_fallback,
        local_auth_token="state-token",
        state_bus=bus,
        browser_session_manager=BrowserSessionManager(),
    )

    response = TestClient(app).get("/control/state", headers={"Authorization": "Bearer state-token"})

    assert response.status_code == 200
    assert response.json()["status"] == "thinking"
    assert response.json()["detail"] == "native-asgi"
    assert "fallback_path" not in response.text


def test_control_plane_asgi_app_mounts_wsgi_fallback_for_non_state_routes() -> None:
    from packages.control_plane_api.asgi_app import create_control_plane_asgi_app

    app = create_control_plane_asgi_app(
        control_wsgi_app=_wsgi_fallback,
        local_auth_token="state-token",
        state_bus=AssistantStateBus(),
        browser_session_manager=BrowserSessionManager(),
    )

    response = TestClient(app).get("/control/health", headers={"Authorization": "Bearer state-token"})

    assert response.status_code == 200
    assert response.json() == {"fallback_path": "/control/health"}


def test_control_plane_asgi_state_route_accepts_shared_browser_cookie() -> None:
    from packages.control_plane_api.asgi_app import create_control_plane_asgi_app

    values: Iterator[str] = iter(("claim-token", "session-token"))
    browser_sessions = BrowserSessionManager(clock=lambda: 1000.0, token_factory=lambda: next(values))
    lease = browser_sessions.create_lease()
    bus = AssistantStateBus()
    control_wsgi_app = create_control_plane_api_app(
        approval_store=InMemoryApprovalStore(),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="state-token",
        state_bus=bus,
        browser_session_manager=browser_sessions,
    )
    app = create_control_plane_asgi_app(
        control_wsgi_app=control_wsgi_app,
        local_auth_token="state-token",
        state_bus=bus,
        browser_session_manager=browser_sessions,
    )
    client = TestClient(app)
    claim_response = client.get(str(lease["claim_url"]), follow_redirects=False)

    assert claim_response.status_code == 302

    response = client.get("/control/state")

    assert response.status_code == 200
    assert response.json()["status"] == "idle"


def test_control_plane_asgi_state_route_rejects_invalid_auth() -> None:
    from packages.control_plane_api.asgi_app import create_control_plane_asgi_app

    app = create_control_plane_asgi_app(
        control_wsgi_app=_wsgi_fallback,
        local_auth_token="state-token",
        state_bus=AssistantStateBus(),
        browser_session_manager=BrowserSessionManager(),
    )

    response = TestClient(app).get("/control/state", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401
    assert response.json()["details"]["reason"] == "invalid"


def test_control_plane_asgi_state_stream_yields_updates_and_unsubscribes() -> None:
    from packages.control_plane_api.asgi_app import iter_state_sse_frames

    async def run() -> None:
        bus = AssistantStateBus()
        frames = iter_state_sse_frames(state_bus=bus, heartbeat_interval_seconds=60.0)
        first = await anext(frames)
        bus.publish_status(AssistantStatusKind.WORKING, detail="native-stream")
        second = await asyncio.wait_for(anext(frames), timeout=1.0)
        await frames.aclose()

        assert json.loads(first.removeprefix("data: ").strip())["status"] == "idle"
        payload = json.loads(second.removeprefix("data: ").strip())
        assert payload["status"] == "working"
        assert payload["detail"] == "native-stream"
        assert bus.safe_projection()["subscriber_count"] == 0

    asyncio.run(run())
