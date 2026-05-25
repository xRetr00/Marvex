from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient

from packages.contracts.state_event import AssistantStatusKind
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from packages.control_plane_api.browser_session import BrowserSessionManager
from packages.session_runtime import BackendSessionCoordinator
from packages.state_bus import AssistantStateBus
from tests.control_plane_api.asgi_helpers import create_control_plane_test_app


def _app(
    *,
    local_auth_token: str = "state-token",
    state_bus: AssistantStateBus | None = None,
    browser_session_manager: BrowserSessionManager | None = None,
    session_coordinator: BackendSessionCoordinator | None = None,
    web_dist: str | None = None,
):
    return create_control_plane_test_app(
        approval_store=InMemoryApprovalStore(),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token=local_auth_token,
        state_bus=state_bus or AssistantStateBus(),
        browser_session_manager=browser_session_manager or BrowserSessionManager(),
        session_coordinator=session_coordinator,
        web_dist=web_dist,
    )


def test_control_plane_asgi_state_route_uses_native_state_snapshot() -> None:
    bus = AssistantStateBus()
    bus.publish_status(AssistantStatusKind.THINKING, detail="native-asgi")
    app = _app(state_bus=bus)

    response = TestClient(app).get("/control/state", headers={"Authorization": "Bearer state-token"})

    assert response.status_code == 200
    assert response.json()["status"] == "thinking"
    assert response.json()["detail"] == "native-asgi"


def test_control_plane_asgi_diagnostics_route_is_native() -> None:
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore(),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="state-token",
        state_bus=AssistantStateBus(),
        browser_session_manager=BrowserSessionManager(),
        diagnostics={"runtime": "control-plane", "status": "ok"},
    )

    response = TestClient(app).get("/control/diagnostics", headers={"Authorization": "Bearer state-token"})

    assert response.status_code == 200
    assert response.json()["runtime"] == "control-plane"
    assert response.json()["status"] == "ok"


def test_control_plane_asgi_app_no_longer_uses_wsgi_middleware() -> None:
    app = _app()
    mounted_apps = [getattr(route, "app", None) for route in app.routes]

    assert all(
        mounted_app is None or mounted_app.__class__.__name__ != "WSGIMiddleware"
        for mounted_app in mounted_apps
    )


def test_control_plane_asgi_serves_static_spa_without_runtime_dispatch(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<main>control shell</main>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('control');", encoding="utf-8")
    app = _app(web_dist=str(tmp_path))
    client = TestClient(app)

    root = client.get("/")
    asset = client.get("/assets/app.js")
    spa_fallback = client.get("/settings")

    assert root.status_code == 200
    assert root.text == "<main>control shell</main>"
    assert asset.status_code == 200
    assert asset.text == "console.log('control');"
    assert spa_fallback.status_code == 200
    assert spa_fallback.text == "<main>control shell</main>"


def test_control_plane_asgi_health_and_version_routes_are_native() -> None:
    client = TestClient(_app())

    health = client.get("/control/health", headers={"Authorization": "Bearer state-token"})
    version = client.get("/control/version", headers={"Authorization": "Bearer state-token"})

    assert health.status_code == 200
    assert health.json() == {"schema_version": "1", "status": "ok"}
    assert version.status_code == 200
    assert version.json() == {"schema_version": "1", "service": "marvex-control-plane-api"}


def test_control_plane_asgi_state_route_accepts_shared_browser_cookie() -> None:
    values: Iterator[str] = iter(("claim-token", "session-token"))
    browser_sessions = BrowserSessionManager(clock=lambda: 1000.0, token_factory=lambda: next(values))
    lease = browser_sessions.create_lease()
    app = _app(browser_session_manager=browser_sessions)
    client = TestClient(app)
    claim_response = client.get(str(lease["claim_url"]), follow_redirects=False)

    assert claim_response.status_code == 302

    response = client.get("/control/state")

    assert response.status_code == 200
    assert response.json()["status"] == "idle"


def test_control_plane_asgi_state_route_rejects_invalid_auth() -> None:
    response = TestClient(_app()).get("/control/state", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401
    assert response.json()["details"]["reason"] == "invalid"


def test_control_plane_asgi_browser_session_routes_are_native_and_cookie_authenticates() -> None:
    values: Iterator[str] = iter(("claim-token", "session-token"))
    browser_sessions = BrowserSessionManager(clock=lambda: 1000.0, token_factory=lambda: next(values))
    app = _app(
        browser_session_manager=browser_sessions,
        session_coordinator=BackendSessionCoordinator(),
    )
    client = TestClient(app)

    lease_response = client.post("/control/browser-session/leases", headers={"Authorization": "Bearer state-token"})
    assert lease_response.status_code == 200
    lease = lease_response.json()
    assert lease["claim_url"] == "/control/browser-session/claim?claim=claim-token"
    assert lease["token_value_logged"] is False
    assert "state-token" not in lease_response.text

    claim_response = client.get(lease["claim_url"], follow_redirects=False)
    assert claim_response.status_code == 302
    assert claim_response.json() == {}
    assert "HttpOnly" in claim_response.headers["set-cookie"]
    assert "SameSite=Strict" in claim_response.headers["set-cookie"]

    cookie_response = client.get("/control/sessions")
    assert cookie_response.status_code == 200
    assert cookie_response.json()["schema_version"] == "1"


def test_control_plane_asgi_browser_session_claim_is_one_time() -> None:
    values: Iterator[str] = iter(("claim-token", "session-token"))
    browser_sessions = BrowserSessionManager(clock=lambda: 1000.0, token_factory=lambda: next(values))
    app = _app(
        browser_session_manager=browser_sessions,
        session_coordinator=BackendSessionCoordinator(),
    )
    client = TestClient(app)
    lease = client.post("/control/browser-session/leases", headers={"Authorization": "Bearer state-token"}).json()

    assert client.get(lease["claim_url"], follow_redirects=False).status_code == 302
    second_claim = client.get(lease["claim_url"], follow_redirects=False)

    assert second_claim.status_code == 401
    assert second_claim.json()["details"]["reason"] == "invalid_browser_session_claim"


def test_control_plane_asgi_session_routes_are_native_safe_projections() -> None:
    coordinator = BackendSessionCoordinator(clock=lambda: 1770000000000, id_factory=lambda: "session-native")
    coordinator.create_session(title="Existing native session")
    app = _app(session_coordinator=coordinator)
    client = TestClient(app)

    list_response = client.get("/control/sessions", headers={"Authorization": "Bearer state-token"})
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["session_count"] == 1
    assert listed["sessions"][0]["title"] == "Existing native session"
    assert listed["transcript_persisted"] is False
    assert "state-token" not in list_response.text.lower()

    create_response = client.post(
        "/control/sessions",
        headers={"Authorization": "Bearer state-token"},
        json={"title": "Created native session"},
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["session"]["title"] == "Created native session"
    assert created["session"]["session_ref"] == {"ref_type": "session", "ref_id": "session-native"}
    assert created["transcript_persisted"] is False


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
