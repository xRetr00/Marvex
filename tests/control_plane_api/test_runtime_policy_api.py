from __future__ import annotations

import io
import json
from wsgiref.util import setup_testing_defaults

from packages.capability_runtime import AutonomyAction, AutonomyMode, AutonomyPolicy, evaluate_autonomy_action
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore, create_control_plane_api_app


def _call(app, path: str, *, method: str = "GET", token: str | None = "fake-control-token", body: dict | None = None):
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    raw = json.dumps(body or {}).encode("utf-8")
    environ["wsgi.input"] = io.BytesIO(raw)
    environ["CONTENT_LENGTH"] = str(len(raw))
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(response)


def test_control_plane_runtime_policy_exposes_mode_matrix_and_audit() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)
    audit = evaluate_autonomy_action(policy, AutonomyAction(action="scheduled connector sync", resource_type="connector", capability="auto_fetch", connector_id="github"))
    app = create_control_plane_api_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        autonomy_policy=policy,
        policy_audit_records=(audit,),
    )

    status, _headers, payload = _call(app, "/control/runtime-policy")
    audit_status, _audit_headers, audit_payload = _call(app, "/control/runtime-policy/audit")

    assert status == "200 OK"
    assert payload["mode"] == "auto_marvex"
    assert payload["matrix"]["web_search"] == "allow"
    assert payload["matrix"]["auto_fetch"] == "allow"
    assert payload["matrix"]["mcp_execute"] == "allow"
    assert payload["hard_block_blacklist_only"] is True
    assert payload["raw_payload_persisted"] is False
    assert audit_status == "200 OK"
    assert audit_payload["audit_records"][0]["decision"] == "allow"
    assert audit_payload["audit_records"][0]["connector_id"] == "github"
    assert "token" not in json.dumps({"policy": payload, "audit": audit_payload}).lower()


def test_control_plane_runtime_policy_mode_update_changes_policy_without_execution() -> None:
    app = create_control_plane_api_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.LOCKED_DOWN),
    )

    status, _headers, payload = _call(app, "/control/runtime-policy", method="POST", body={"mode": "ask_before_risky"})
    read_status, _read_headers, read_payload = _call(app, "/control/runtime-policy")

    assert status == "200 OK"
    assert payload["mode"] == "ask_before_risky"
    assert payload["policy_update_started"] is True
    assert payload["execution_started"] is False
    assert read_status == "200 OK"
    assert read_payload["mode"] == "ask_before_risky"
    assert read_payload["matrix"]["file_delete"] == "ask"
