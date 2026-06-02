from __future__ import annotations

import json

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from tests.control_plane_api.asgi_helpers import asgi_call, create_control_plane_test_app


def _call(app, path: str, *, method: str = "GET", body: dict | None = None):
    status, _headers, payload = asgi_call(app, path, method=method, body=body)
    return status, payload


def _app():
    return create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
    )


def test_control_plane_agent_and_persona_catalogs_are_not_control_plane_routes() -> None:
    app = _app()

    agent_status, agents = _call(app, "/control/agents")
    persona_status, personas = _call(app, "/control/personas")

    assert agent_status == "404 Not Found"
    assert persona_status == "404 Not Found"
    assert agents["details"]["reason"] == "not_found"
    assert personas["details"]["reason"] == "not_found"
    serialized = json.dumps({"agents": agents, "personas": personas}).lower()
    assert "secret" not in serialized
    assert "raw_payload\": true" not in serialized


def test_control_plane_agent_and_persona_selection_routes_are_removed() -> None:
    app = _app()

    agent_status, agent_payload = _call(app, "/control/agents/active", method="POST", body={"agent_id": "agent.deep_search"})
    persona_status, persona_payload = _call(app, "/control/personas/active", method="POST", body={"persona_id": "persona.marvex.female"})

    assert agent_status == "404 Not Found"
    assert agent_payload["details"]["reason"] == "not_found"
    assert persona_status == "404 Not Found"
    assert persona_payload["details"]["reason"] == "not_found"
