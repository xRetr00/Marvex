from __future__ import annotations

import json

from packages.capability_runtime import AutonomyAction, AutonomyMode, AutonomyPolicy, evaluate_autonomy_action
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from tests.control_plane_api.asgi_helpers import asgi_call as _call, create_control_plane_test_app


def test_control_plane_runtime_policy_exposes_mode_matrix_and_audit() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)
    audit = evaluate_autonomy_action(policy, AutonomyAction(action="scheduled connector sync", resource_type="connector", capability="auto_fetch", connector_id="github"))
    app = create_control_plane_test_app(
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
    assert payload["matrix"]["file_delete"] == "allow"
    assert payload["matrix"]["shell_command_execution"] == "allow"
    assert payload["hard_block_blacklist_only"] is True
    assert payload["raw_payload_persisted"] is False
    assert audit_status == "200 OK"
    assert audit_payload["audit_records"][0]["decision"] == "allow"
    assert audit_payload["audit_records"][0]["connector_id"] == "github"
    assert "token" not in json.dumps({"policy": payload, "audit": audit_payload}).lower()


def test_control_plane_runtime_policy_mode_update_changes_policy_without_execution() -> None:
    app = create_control_plane_test_app(
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


def test_control_plane_runtime_policy_update_rejects_permission_matrix_payloads() -> None:
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY),
    )

    status, _headers, payload = _call(
        app,
        "/control/runtime-policy",
        method="POST",
        body={"mode": "custom", "matrix": {"shell_command_execution": "allow"}},
    )

    assert status == "400 Bad Request"
    assert payload["details"]["reason"] == "invalid_runtime_policy_mode"
