from __future__ import annotations

from packages.capability_runtime.governance_audit import GovernanceAction, GovernanceDecisionType, GranularPermission, classify_governance_action


def test_governance_audit_trail_explains_allow_approval_quarantine_and_hard_block() -> None:
    read = classify_governance_action(GovernanceAction(requested_action="read public page", capability="browser.read", permission=GranularPermission.PUBLIC_READ))
    delete = classify_governance_action(GovernanceAction(requested_action="delete file", capability="file.delete", permission=GranularPermission.WRITE_LOCAL))
    prompt_attack = classify_governance_action(GovernanceAction(requested_action="exploit prompt injection", capability="policy", permission=GranularPermission.POLICY_OVERRIDE))
    command_attack = classify_governance_action(GovernanceAction(requested_action="command injection exfiltrate data", capability="shell", permission=GranularPermission.EXECUTE_COMMAND))

    assert read.decision == GovernanceDecisionType.ALLOW
    assert delete.decision == GovernanceDecisionType.APPROVAL_REQUIRED
    assert prompt_attack.decision in {GovernanceDecisionType.QUARANTINE, GovernanceDecisionType.HARD_BLOCK}
    assert command_attack.decision == GovernanceDecisionType.HARD_BLOCK
    for decision in (read, delete, prompt_attack, command_attack):
        projection = decision.safe_projection()
        assert projection.reason_codes
        assert projection.raw_payload_persisted is False
        assert projection.policy_source == "packages.capability_runtime.governance_audit"


def test_browser_read_allowed_click_requires_approval_and_arbitrary_execution_denied_or_approval() -> None:
    browser_read = classify_governance_action(GovernanceAction(requested_action="browser read page text", capability="browser.read", permission=GranularPermission.PUBLIC_READ))
    click = classify_governance_action(GovernanceAction(requested_action="browser click button", capability="browser.click", permission=GranularPermission.BROWSER_SIDE_EFFECT))
    arbitrary_tool = classify_governance_action(GovernanceAction(requested_action="execute arbitrary external tool", capability="tool.unknown", permission=GranularPermission.ARBITRARY_EXECUTION))

    assert browser_read.decision == GovernanceDecisionType.ALLOW
    assert click.decision == GovernanceDecisionType.APPROVAL_REQUIRED
    assert arbitrary_tool.decision in {GovernanceDecisionType.APPROVAL_REQUIRED, GovernanceDecisionType.DENY}
    assert arbitrary_tool.required_permission == GranularPermission.ARBITRARY_EXECUTION
