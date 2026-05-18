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
from datetime import UTC, datetime
from urllib.parse import urlencode

from packages.contracts import ConversationRef, SessionRef, TraceEvent, TraceLevel, TraceStage
from packages.marketplace_runtime import (
    McpMarketplaceCatalog,
    McpMarketplaceEntry,
    McpRegistryToolSummary,
    SkillMarketplaceCatalog,
    SkillMarketplaceEntry,
)
from packages.memory_runtime import MemoryRecord, MemoryRef
from packages.skills_runtime import SkillManifest, SkillPromptContribution, SkillRef, SkillResourceKind, SkillResourceRef
from packages.telemetry.trace_reader import InMemoryTraceReader
from packages.memory_runtime import CurrentProcessMemoryStore


def _skill_manifest() -> SkillManifest:
    skill_ref = SkillRef(skill_id="test.safe_skill")
    return SkillManifest(
        schema_version="1",
        skill_ref=skill_ref,
        display_name="Safe Test Skill",
        description="Local package metadata only",
        instruction_ref=SkillResourceRef(kind=SkillResourceKind.INSTRUCTION, uri="local://skills/test.safe_skill/SKILL.md"),
        prompt_contributions=(SkillPromptContribution(
            schema_version="1",
            contribution_id="test.safe_skill.context",
            skill_ref=skill_ref,
            summary="Use deterministic local fixtures.",
            when_to_use="When testing marketplace metadata.",
            max_context_chars=120,
        ),),
    )


def _expanded_app():
    store = InMemoryApprovalStore.from_requests((_approval_request(),))
    store.approve("approval-request-1", reason="record approval history")
    approval_store = InMemoryApprovalStore.from_requests((_approval_request(),))
    memory_store = CurrentProcessMemoryStore()
    memory_store.write_record(MemoryRecord(
        schema_version="1",
        memory_ref=MemoryRef(ref_type="memory", ref_id="memory-1"),
        scope="session",
        memory_kind="fact",
        session_ref=SessionRef(ref_type="session", ref_id="session-1"),
        conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-1"),
        trace_id="trace-1",
        turn_id="turn-1",
        content="User prefers concise status updates.",
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 18, tzinfo=UTC),
    ))
    trace_reader = InMemoryTraceReader()
    trace_reader.emit(TraceEvent(
        schema_version="1",
        trace_id="trace-1",
        event_id="turn-1:complete",
        timestamp=datetime(2026, 5, 18, tzinfo=UTC),
        stage=TraceStage.TURN_COMPLETED,
        level=TraceLevel.INFO,
        message="turn completed",
        data={
            "status": "completed",
            "session_ref": {"ref_type": "session", "ref_id": "session-1"},
            "conversation_ref": {"ref_type": "conversation", "ref_id": "conversation-1"},
            "approval_status": "pending",
        },
    ))
    mcp_catalog = McpMarketplaceCatalog.from_entries((McpMarketplaceEntry(
        schema_version="1",
        registry_name="official_mcp_registry",
        server_id="local-test-mcp",
        display_name="Local Test MCP",
        description="Official registry metadata cache for test server",
        registry_url="https://registry.modelcontextprotocol.io/servers/local-test-mcp",
        tool_summaries=(McpRegistryToolSummary(name="calculator", description="Safe helper"),),
        transport_summaries=("stdio",),
    ),))
    skills_catalog = SkillMarketplaceCatalog.from_entries((SkillMarketplaceEntry.from_manifest(_skill_manifest(), source="approved_local"),))
    return create_control_plane_api_app(
        approval_store=approval_store,
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        approval_history=store.list_history().decisions,
        mcp_marketplace=mcp_catalog,
        skills_marketplace=skills_catalog,
        memory_store=memory_store,
        trace_reader=trace_reader,
        trace_ids=("trace-1",),
        policy_views=({"policy_id": "browser-actions", "risk_level": "high", "approval_required": True},),
        diagnostics={"runtime": "control_plane", "status": "ok", "remote_binding": False},
    )


def test_control_plane_marketplace_endpoints_are_read_only_and_auth_protected() -> None:
    app = _expanded_app()

    unauth_status, _headers, unauth_payload = _call(app, "/control/marketplace/mcp", token=None)
    status, _headers, payload = _call(app, "/control/marketplace/mcp")
    proposal_status, _proposal_headers, proposal = _call(app, "/control/marketplace/mcp/local-test-mcp/allowlist-proposals", method="POST")
    disable_status, _disable_headers, disable_payload = _call(app, "/control/marketplace/mcp/local-test-mcp/disable", method="POST")

    assert unauth_status == "401 Unauthorized"
    assert unauth_payload["code"] == "AUTH_REQUIRED"
    assert status == "200 OK"
    assert payload["entries"][0]["read_only_browse"] is True
    assert payload["entries"][0]["install_allowed"] is False
    assert proposal_status == "200 OK"
    assert proposal["requires_human_approval"] is True
    assert proposal["install_started"] is False
    assert proposal["launch_started"] is False
    assert disable_status == "200 OK"
    assert disable_payload["enabled"] is False


def test_control_plane_skills_marketplace_preview_and_enable_are_safe() -> None:
    app = _expanded_app()

    status, _headers, payload = _call(app, "/control/marketplace/skills")
    enable_status, _enable_headers, enable_payload = _call(app, "/control/marketplace/skills/test.safe_skill/enable", method="POST")
    disable_status, _disable_headers, disable_payload = _call(app, "/control/marketplace/skills/test.safe_skill/disable", method="POST")

    assert status == "200 OK"
    assert payload["entries"][0]["skill_id"] == "test.safe_skill"
    assert payload["entries"][0]["script_execution_allowed"] is False
    assert payload["previews"][0]["raw_instruction_persisted"] is False
    assert enable_status == "200 OK"
    assert enable_payload["enabled"] is True
    assert enable_payload["execution_started"] is False
    assert disable_status == "200 OK"
    assert disable_payload["enabled"] is False


def test_control_plane_memory_inspect_and_forget_are_safe() -> None:
    app = _expanded_app()

    status, _headers, payload = _call(app, "/control/memory")
    forget_status, _forget_headers, forget_payload = _call(app, "/control/memory/memory-1/forget", method="POST")

    assert status == "200 OK"
    assert payload["records"][0]["content_preview"] == "User prefers concise status updates."
    assert payload["records"][0]["raw_transcript_persisted"] is False
    assert forget_status == "200 OK"
    assert forget_payload["forgotten"] is True


def test_control_plane_trace_search_history_policies_and_diagnostics_are_safe() -> None:
    app = _expanded_app()
    query = urlencode({"session_ref_id": "session-1", "approval_status": "pending"})

    trace_status, _trace_headers, traces = _call(app, f"/control/traces/search?{query}")
    history_status, _history_headers, history = _call(app, "/control/approvals/history")
    policies_status, _policy_headers, policies = _call(app, "/control/policies")
    diagnostics_status, _diagnostics_headers, diagnostics = _call(app, "/control/diagnostics")

    assert trace_status == "200 OK"
    assert traces["match_count"] == 1
    assert history_status == "200 OK"
    assert history["decision_count"] == 1
    assert policies_status == "200 OK"
    assert policies["policies"][0]["approval_required"] is True
    assert diagnostics_status == "200 OK"
    assert diagnostics["remote_binding"] is False
    serialized = json.dumps({"traces": traces, "history": history, "policies": policies, "diagnostics": diagnostics}).lower()
    assert "secret" not in serialized
    assert "raw_payload\": true" not in serialized
