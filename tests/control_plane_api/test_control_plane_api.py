from __future__ import annotations

import io
import json
from wsgiref.util import setup_testing_defaults

from packages.capability_runtime import (
    ApprovalPrompt,
    CapabilityApprovalRequest,
    CapabilityExecutionMode,
    CapabilityKind,
    CapabilityRef,
    PendingApprovalState,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.control_plane_api import (
    ControlPlaneSnapshot,
    InMemoryApprovalStore,
    create_control_plane_api_app,
)


def _approval_request() -> CapabilityApprovalRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click")
    return CapabilityApprovalRequest(
        schema_version="1",
        approval_request_id="approval-request-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=ref,
        prompt=ApprovalPrompt(
            schema_version="1",
            prompt_id="approval-prompt-1",
            capability_ref=ref,
            user_visible_summary="Allow browser click on the active page?",
            risk_level=ToolRiskLevel.HIGH,
            side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
        ),
    )


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


def _app():
    store = InMemoryApprovalStore.from_requests((_approval_request(),))
    snapshot = ControlPlaneSnapshot.foundation_default(
        schema_version="1",
        providers=(
            {"provider_id": "lmstudio_responses", "configured": True, "secret_present": True},
        ),
        capabilities=(
            {"identifier": "builtin.calculator", "kind": "tool", "risk_level": "safe"},
        ),
        tools=(
            {"tool_id": "builtin.calculator", "side_effect_level": "read_only"},
        ),
        mcp_servers=(
            {"server_id": "local-test-mcp", "allowlisted": True, "tool_count": 1},
        ),
        skills=(
            {"skill_id": "test.fake_skill", "validated": True},
        ),
        traces=(
            {"trace_id": "trace-1", "event_count": 2, "raw_payload_persisted": False},
        ),
        memory=(
            {"memory_ref": "memory:1", "record_count": 1},
        ),
        sessions=(
            {"session_id": "session-1", "conversation_count": 1},
        ),
        agent_loops=(
            {"loop_id": "loop-1", "step_count": 1, "stop_reason": "waiting_for_human_approval"},
        ),
        telemetry={"trace_count": 1, "raw_payload_persisted": False},
        settings={"browser_tools_enabled": False, "computer_use_enabled": False},
    )
    return create_control_plane_api_app(
        approval_store=store,
        snapshot=snapshot,
        local_auth_token="fake-control-token",
    )


def test_control_plane_requires_auth_without_echoing_token() -> None:
    app = _app()

    status, _headers, payload = _call(app, "/control/approvals", token=None)

    assert status == "401 Unauthorized"
    serialized = json.dumps(payload)
    assert "fake-control-token" not in serialized
    assert payload["code"] == "AUTH_REQUIRED"


def test_list_and_read_pending_approvals_are_safe_projections() -> None:
    app = _app()

    status, _headers, payload = _call(app, "/control/approvals")
    detail_status, _detail_headers, detail = _call(app, "/control/approvals/approval-request-1")

    assert status == "200 OK"
    assert payload["pending_count"] == 1
    assert payload["approvals"][0]["risk_level"] == "high"
    assert payload["approvals"][0]["execution_mode"] == CapabilityExecutionMode.REQUIRES_APPROVAL.value
    assert payload["raw_payload_persisted"] is False
    assert detail_status == "200 OK"
    assert detail["approval_request_id"] == "approval-request-1"
    assert detail["capability_summary"] == {"kind": "tool", "identifier": "browser.click"}
    assert "selector" not in json.dumps(detail).lower()
    assert "token" not in json.dumps(detail).lower()


def test_approve_and_deny_transition_pending_state_without_execution() -> None:
    app = _app()

    approve_status, _approve_headers, approve_payload = _call(
        app,
        "/control/approvals/approval-request-1/approve",
        method="POST",
        body={"reason": "user confirmed safe test click"},
    )
    list_status, _list_headers, list_payload = _call(app, "/control/approvals")

    assert approve_status == "200 OK"
    assert approve_payload["decision"] == "approved"
    assert approve_payload["execution_started"] is False
    assert approve_payload["raw_payload_persisted"] is False
    assert list_status == "200 OK"
    assert list_payload["pending_count"] == 0

    app = _app()
    deny_status, _deny_headers, deny_payload = _call(
        app,
        "/control/approvals/approval-request-1/deny",
        method="POST",
        body={"reason": "not safe enough"},
    )

    assert deny_status == "200 OK"
    assert deny_payload["decision"] == "denied"
    assert deny_payload["execution_started"] is False


def test_control_plane_snapshot_exposes_safe_views_only() -> None:
    app = _app()

    status, _headers, payload = _call(app, "/control/snapshot")

    assert status == "200 OK"
    assert payload["providers"][0] == {
        "provider_id": "lmstudio_responses",
        "configured": True,
        "secret_present": True,
        "secret_value_present": False,
    }
    assert payload["approvals"]["pending_count"] == 1
    assert payload["settings"] == {"browser_tools_enabled": False, "computer_use_enabled": False}
    serialized = json.dumps(payload).lower()
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    assert "transcript" not in serialized
    assert "raw_payload\": true" not in serialized


def test_pending_approval_state_still_comes_from_capability_runtime() -> None:
    request = _approval_request()
    pending = PendingApprovalState.from_request(request)

    assert pending.approval_request_id == "approval-request-1"
    assert pending.raw_prompt_persisted is False