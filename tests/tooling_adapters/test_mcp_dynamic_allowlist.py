from __future__ import annotations

from packages.adapters.capabilities.mcp import McpAllowlistPolicy, McpAllowlistProposal, McpServerRef, McpToolRef, McpTransport


def test_mcp_allowlist_policy_can_be_projected_from_runtime_state_and_audits_changes() -> None:
    policy = McpAllowlistPolicy.from_runtime_config(policy_id="mcp.policy.local", allowed_server_ids=("local-test",), allowed_tool_names=("safe_lookup",), source="control_plane")
    server = McpServerRef(server_id="local-test", transport=McpTransport.STDIO, origin="manual_test_fixture")
    allowed_tool = McpToolRef(server_ref=server, tool_name="safe_lookup")
    blocked_tool = McpToolRef(server_ref=server, tool_name="run_shell")

    assert policy.to_allowlist().allows(allowed_tool) is True
    assert policy.to_allowlist().allows(blocked_tool) is False
    projection = policy.safe_projection()
    assert projection["policy_source"] == "control_plane"
    assert projection["raw_config_persisted"] is False


def test_mcp_allowlist_change_proposal_is_reviewable_not_silent_mutation() -> None:
    proposal = McpAllowlistProposal.propose_add_tool(policy_id="mcp.policy.local", server_id="local-test", tool_name="safe_lookup", requested_by="control_plane")

    assert proposal.review_required is True
    assert proposal.applied_without_review is False
    assert proposal.safe_projection()["tool_name"] == "safe_lookup"
