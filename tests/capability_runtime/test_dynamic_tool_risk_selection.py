from packages.capability_runtime import ActionPermission, AutonomyAction, AutonomyMode, AutonomyPolicy, PolicyDecision, ToolRiskLevel, evaluate_autonomy_action
from packages.capability_runtime.selection import ToolSelectionRequest, ToolRegistryEntry, select_tools_for_request
from packages.intent_runtime import IntentKind


def _tools() -> tuple[ToolRegistryEntry, ...]:
    return (
        ToolRegistryEntry(name="builtin.calculator", description="Evaluate arithmetic.", intent_tags=(IntentKind.CAPABILITY_TOOL.value,), risk=ToolRiskLevel.SAFE, approval_requirement="none", input_schema={"type": "object"}),
        ToolRegistryEntry(name="browser.extract_text", description="Read public browser page text.", intent_tags=(IntentKind.BROWSER_COMPUTER_USE.value,), risk=ToolRiskLevel.LOW, approval_requirement="policy", input_schema={"type": "object"}),
        ToolRegistryEntry(name="mcp.safe_lookup", description="Read-only MCP lookup.", intent_tags=(IntentKind.MCP_NEEDED.value,), risk=ToolRiskLevel.LOW, approval_requirement="policy", input_schema={"type": "object"}, mcp_server_id="local-test"),
        ToolRegistryEntry(name="web.search", description="Search current public web evidence.", intent_tags=(IntentKind.WEB_SEARCH.value, IntentKind.GROUNDED_ANSWER.value), risk=ToolRiskLevel.LOW, approval_requirement="none", input_schema={"type": "object"}),
    )


def test_dynamic_tool_selection_filters_by_intent_availability_policy_and_failures() -> None:
    policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)

    calculator = select_tools_for_request(ToolSelectionRequest(intent_kind=IntentKind.CAPABILITY_TOOL, autonomy_policy=policy), _tools())
    browser = select_tools_for_request(ToolSelectionRequest(intent_kind=IntentKind.BROWSER_COMPUTER_USE, autonomy_policy=policy), _tools())
    mcp_blocked = select_tools_for_request(ToolSelectionRequest(intent_kind=IntentKind.MCP_NEEDED, autonomy_policy=policy, mcp_allowlist=()), _tools())
    web_after_failure = select_tools_for_request(ToolSelectionRequest(intent_kind=IntentKind.WEB_SEARCH, autonomy_policy=policy, previous_tool_failures=("web.search",)), _tools())

    assert [tool.name for tool in calculator.eligible_tools] == ["builtin.calculator"]
    assert [tool.name for tool in browser.eligible_tools] == ["browser.extract_text"]
    assert mcp_blocked.eligible_tools == ()
    assert mcp_blocked.excluded_tools[0].reason_code == "tool.mcp_not_allowlisted"
    assert web_after_failure.eligible_tools == ()
    assert web_after_failure.excluded_tools[0].reason_code == "tool.previous_failure"
    assert calculator.provider_tool_schemas[0]["availability"] == "available"
    assert calculator.provider_tool_schemas[0]["input_schema"] == {"type": "object"}


def test_per_request_risk_assessment_allows_asks_denies_and_hard_blocks_by_request() -> None:
    ask_policy = AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY)
    custom_policy = ask_policy.with_permissions(shell_command_execution=ActionPermission.ALLOW, file_delete=ActionPermission.ALLOW)

    public_read = evaluate_autonomy_action(ask_policy, AutonomyAction(action="read public page", resource_type="web_page", capability="browser_read", risk_level=ToolRiskLevel.LOW))
    browser_click = evaluate_autonomy_action(ask_policy, AutonomyAction(action="click public video result", resource_type="web_page", capability="browser_click_type", risk_level=ToolRiskLevel.MEDIUM))
    shell_allowed = evaluate_autonomy_action(custom_policy, AutonomyAction(action="run npm test", resource_type="shell", capability="shell", risk_level=ToolRiskLevel.MEDIUM))
    file_delete_allowed = evaluate_autonomy_action(custom_policy, AutonomyAction(action="delete generated temp file", resource_type="file", capability="delete", risk_level=ToolRiskLevel.HIGH))
    abuse = evaluate_autonomy_action(custom_policy, AutonomyAction(action="use command injection to exfiltrate data", resource_type="shell", capability="shell", risk_level=ToolRiskLevel.CRITICAL))

    assert public_read.decision == PolicyDecision.ALLOW
    assert browser_click.decision == PolicyDecision.APPROVAL_REQUIRED
    assert shell_allowed.decision == PolicyDecision.ALLOW
    assert file_delete_allowed.decision == PolicyDecision.ALLOW
    assert abuse.decision == PolicyDecision.HARD_BLOCK
    assert "policy.blacklist.command_injection" in abuse.reason_codes or "policy.blacklist.data_exfiltration" in abuse.reason_codes
