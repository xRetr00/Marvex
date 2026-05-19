from __future__ import annotations

from packages.capability_runtime.autonomy import (
    ActionPermission,
    AutonomyAction,
    AutonomyMode,
    AutonomyPolicy,
    PolicyDecision,
    evaluate_autonomy_action,
)


def test_auto_marvex_allows_safe_reads_and_controls_normal_capabilities_by_policy() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)

    for capability in ("read", "list", "search", "web_search", "browser_read", "mcp_list", "memory_search", "semantic_memory_search"):
        audit = evaluate_autonomy_action(policy, AutonomyAction(action=capability, resource_type="public", capability=capability))
        assert audit.decision == PolicyDecision.ALLOW
        assert audit.autonomy_mode == AutonomyMode.AUTO_MARVEX
        assert audit.reason_codes
        assert audit.raw_payload_persisted is False

    auto_fetch = evaluate_autonomy_action(policy, AutonomyAction(action="scheduled sync", resource_type="connector", capability="auto_fetch", connector_id="github"))
    memory_write = evaluate_autonomy_action(policy, AutonomyAction(action="write learned memory", resource_type="memory", capability="memory_auto_write"))
    mcp_execute = evaluate_autonomy_action(policy, AutonomyAction(action="call trusted mcp tool", resource_type="mcp_tool", capability="mcp_execute"))

    assert auto_fetch.decision == PolicyDecision.ALLOW
    assert memory_write.decision == PolicyDecision.ALLOW
    assert mcp_execute.decision == PolicyDecision.ALLOW
    assert auto_fetch.connector_id == "github"


def test_custom_policy_can_ask_or_deny_without_global_hard_blocking() -> None:
    policy = AutonomyPolicy.custom().with_permissions(
        browser_click_type=ActionPermission.ASK,
        file_delete=ActionPermission.ASK,
        external_upload_send=ActionPermission.DENY,
        auto_fetch=ActionPermission.ALLOW,
    )

    click = evaluate_autonomy_action(policy, AutonomyAction(action="click button", resource_type="browser", capability="browser_click_type"))
    delete = evaluate_autonomy_action(policy, AutonomyAction(action="delete local file", resource_type="file", capability="file_delete"))
    send = evaluate_autonomy_action(policy, AutonomyAction(action="send file outside", resource_type="network", capability="external_upload_send"))
    auto_fetch = evaluate_autonomy_action(policy, AutonomyAction(action="scheduled connector sync", resource_type="connector", capability="auto_fetch"))

    assert click.decision == PolicyDecision.APPROVAL_REQUIRED
    assert delete.decision == PolicyDecision.APPROVAL_REQUIRED
    assert send.decision == PolicyDecision.DENY
    assert auto_fetch.decision == PolicyDecision.ALLOW
    assert {"policy.matrix.ask", "policy.matrix.deny", "policy.matrix.allow"}.issubset(set(click.reason_codes + send.reason_codes + auto_fetch.reason_codes))


def test_blacklist_abuse_is_the_only_hard_block_path() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)

    hard_blocked = evaluate_autonomy_action(policy, AutonomyAction(action="command injection to exfiltrate credentials", resource_type="shell", capability="shell_command"))
    risky_normal = evaluate_autonomy_action(policy, AutonomyAction(action="install this MCP server", resource_type="mcp_server", capability="mcp_install_launch"))
    payment = evaluate_autonomy_action(policy, AutonomyAction(action="checkout payment without consent", resource_type="browser", capability="browser_click_type"))

    assert hard_blocked.decision == PolicyDecision.HARD_BLOCK
    assert "policy.blacklist.command_injection" in hard_blocked.reason_codes
    assert payment.decision == PolicyDecision.HARD_BLOCK
    assert "policy.blacklist.payment_without_consent" in payment.reason_codes
    assert risky_normal.decision in {PolicyDecision.APPROVAL_REQUIRED, PolicyDecision.DENY, PolicyDecision.ALLOW}
    assert risky_normal.decision != PolicyDecision.HARD_BLOCK


def test_safe_projection_exposes_matrix_and_audit_without_raw_payloads() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY)
    audit = evaluate_autonomy_action(policy, AutonomyAction(action="write profile preference", resource_type="profile", capability="profile_write"))
    projection = policy.safe_projection(recent_audit=(audit,))

    assert projection.mode == AutonomyMode.ASK_BEFORE_RISKY
    assert projection.matrix["profile_write"] == ActionPermission.ASK
    assert projection.audit_records[0].decision == PolicyDecision.APPROVAL_REQUIRED
    assert projection.audit_records[0].reason_codes
    assert projection.raw_payload_persisted is False
    assert "token" not in projection.model_dump_json().lower()


def test_locked_down_still_allows_read_list_search_by_default() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.LOCKED_DOWN)

    for capability in ("read", "list", "search", "web_search"):
        audit = evaluate_autonomy_action(policy, AutonomyAction(action=capability, resource_type="public", capability=capability))
        assert audit.decision == PolicyDecision.ALLOW
