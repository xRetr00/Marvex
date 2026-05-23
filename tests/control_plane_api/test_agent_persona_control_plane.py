from __future__ import annotations

import io
import json
from wsgiref.util import setup_testing_defaults

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore, create_control_plane_api_app


def _call(app, path: str, *, method: str = "GET", body: dict | None = None):
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    environ["HTTP_AUTHORIZATION"] = "Bearer fake-control-token"
    raw = json.dumps(body or {}).encode("utf-8")
    environ["wsgi.input"] = io.BytesIO(raw)
    environ["CONTENT_LENGTH"] = str(len(raw))
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], json.loads(response)


def _app():
    return create_control_plane_api_app(
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
