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


def test_named_policy_objects_match_auto_marvex_matrix() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)

    assert policy.auto_fetch_binding.global_auto_fetch == policy.matrix.auto_fetch == ActionPermission.ALLOW
    assert policy.connector_sync.live_sync == policy.matrix.live_oauth_sync == ActionPermission.ALLOW
    assert policy.connector_sync.auto_fetch == policy.matrix.auto_fetch == ActionPermission.ALLOW
    assert policy.memory_auto_write.memory_auto_write == policy.matrix.memory_auto_write == ActionPermission.ALLOW
    assert policy.profile_write.profile_write == policy.matrix.profile_write == ActionPermission.ALLOW
    assert policy.mcp_execution.execute_tool == policy.matrix.mcp_execute == ActionPermission.ALLOW
    assert policy.skill_execution.update_or_create_skill == policy.matrix.skills_update_create == ActionPermission.ALLOW
    assert policy.browser_computer.click_type == policy.matrix.browser_click_type == ActionPermission.ASK
    assert policy.file_operations.delete_file == policy.matrix.file_delete == ActionPermission.ASK
    assert policy.provider_fallback.provider_retry == policy.matrix.provider_retry_fallback == ActionPermission.ALLOW
    assert policy.learning_mutation.candidate_apply == policy.matrix.learning_mutation_candidates == ActionPermission.ALLOW
    assert policy.learning_mutation.skill_candidate_apply == policy.matrix.learning_mutation_candidates == ActionPermission.ALLOW
    assert policy.learning_mutation.preference_candidate_apply == policy.matrix.learning_mutation_candidates == ActionPermission.ALLOW


def test_owner_safe_policy_auto_allows_safe_agent_tools_but_keeps_side_effects_gated() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.OWNER_SAFE)

    for capability in ("read", "list", "search", "web_search", "memory_search", "semantic_memory_search", "memory_explicit_write", "skills_use"):
        audit = evaluate_autonomy_action(policy, AutonomyAction(action=capability, resource_type="agent_tool", capability=capability))
        assert audit.decision == PolicyDecision.ALLOW

    for capability in ("file_write", "file_delete", "browser_click_type", "computer_actions", "mcp_execute", "connectors_oauth", "external_upload_send", "shell_command_execution", "memory_auto_write"):
        audit = evaluate_autonomy_action(policy, AutonomyAction(action=capability, resource_type="side_effect", capability=capability))
        assert audit.decision == PolicyDecision.APPROVAL_REQUIRED


def test_policy_decision_audit_contains_required_traceable_fields() -> None:
    policy = AutonomyPolicy.custom().with_permissions(file_delete=ActionPermission.QUARANTINE)
    audit = evaluate_autonomy_action(
        policy,
        AutonomyAction(
            action="delete generated artifact",
            resource_type="file",
            capability="file_delete",
            connector_id="local-files",
            source_id="workspace",
            safe_trace_ref="trace-policy-1",
            user_approval_state="pending",
            timestamp="2026-05-19T00:00:00Z",
        ),
    )

    projection = audit.safe_projection()

    assert projection["decision_id"]
    assert projection["autonomy_mode"] == "custom"
    assert projection["action"] == "delete generated artifact"
    assert projection["resource_type"] == "file"
    assert projection["capability"] == "file_delete"
    assert projection["connector_id"] == "local-files"
    assert projection["source_id"] == "workspace"
    assert projection["risk_level"] == "critical"
    assert projection["reason_codes"] == ["policy.matrix.quarantine"]
    assert projection["user_approval_state"] == "pending"
    assert projection["policy_source"] == "packages.capability_runtime.autonomy"
    assert projection["timestamp"] == "2026-05-19T00:00:00Z"
    assert projection["safe_trace_ref"] == "trace-policy-1"
    assert projection["raw_payload_persisted"] is False
