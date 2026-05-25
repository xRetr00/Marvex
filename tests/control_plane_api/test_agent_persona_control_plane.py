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


def test_control_plane_exposes_backend_agent_and_persona_catalogs_for_future_combo_boxes() -> None:
    app = _app()

    agent_status, agents = _call(app, "/control/agents")
    persona_status, personas = _call(app, "/control/personas")

    assert agent_status == "200 OK"
    assert persona_status == "200 OK"
    assert agents["active_agent_id"] == "agent.main.marvex"
    assert agents["agent_count"] == 6
    assert agents["agents"][0]["agent_id"] == "agent.main.marvex"
    assert any(agent["agent_id"] == "agent.deep_search" and agent["direct_selectable"] for agent in agents["agents"])
    assert any(agent["agent_id"] == "agent.verifier" for agent in agents["agents"])
    assert personas["active_persona_id"] == "persona.marvex.female"
    assert personas["personas"][0]["voice_id"] == "af_heart"
    serialized = json.dumps({"agents": agents, "personas": personas}).lower()
    assert "secret" not in serialized
    assert "raw_payload\": true" not in serialized


def test_control_plane_agent_and_persona_selection_are_safe_non_executing_requests() -> None:
    app = _app()

    agent_status, agent_payload = _call(app, "/control/agents/active", method="POST", body={"agent_id": "agent.deep_search"})
    persona_status, persona_payload = _call(app, "/control/personas/active", method="POST", body={"persona_id": "persona.marvex.female"})

    assert agent_status == "200 OK"
    assert agent_payload["active_agent_id"] == "agent.deep_search"
    assert agent_payload["execution_started"] is False
    assert persona_status == "200 OK"
    assert persona_payload["active_persona_id"] == "persona.marvex.female"
    assert persona_payload["voice_id"] == "af_heart"
    assert persona_payload["execution_started"] is False
