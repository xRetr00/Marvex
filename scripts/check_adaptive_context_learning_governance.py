from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _intent(kind):
    from packages.intent_runtime import IntentRef

    return IntentRef(intent_id=f"intent.{kind.value}", intent_kind=kind)


def _candidate(kind, identifier: str, summary: str, tags: tuple[str, ...], tokens: int = 20):
    from packages.context_runtime import ContextCandidate, ContextSourceRef

    return ContextCandidate.from_safe_summary(ContextSourceRef(kind=kind, identifier=identifier), summary, token_estimate=tokens, intent_tags=tags)


def main() -> int:
    failures: list[str] = []
    try:
        from packages.capability_runtime import CapabilityKind, CapabilityManifest, CapabilityRef, ToolRiskLevel
        from packages.capability_runtime.governance_audit import GovernanceAction, GovernanceDecisionType, GranularPermission, classify_governance_action
        from packages.context_runtime import ContextSourceKind
        from packages.intent_runtime import IntentKind
        from packages.prompt_harness_runtime import PromptAssemblyRequest, PromptSectionKind
        from packages.prompt_harness_runtime.adaptive import AdaptivePromptRoute, adaptive_context_policy_for_route, assemble_adaptive_prompt_harness, tool_schema_context_candidate
        from packages.learning_runtime import FeedbackEvent, LearningLoop, UserCorrection
        from packages.adapters.capabilities.mcp import McpAllowlistProposal, McpAllowlistPolicy
    except Exception as exc:
        failures.append(f"adaptive runtime import failed: {type(exc).__name__}")
    else:
        grounded_intent = _intent(IntentKind.GROUNDED_ANSWER)
        grounded_policy = adaptive_context_policy_for_route(AdaptivePromptRoute.GROUNDED_LOOKUP)
        evidence = _candidate(ContextSourceKind.WEB_SEARCH_EVIDENCE, "web.evidence.gate", "[web.evidence.1] safe evidence", (IntentKind.GROUNDED_ANSWER.value,))
        grounded = assemble_adaptive_prompt_harness(PromptAssemblyRequest(schema_version="1", trace_id="trace-gate", turn_id="turn-gate", intent_ref=grounded_intent, context_pack=grounded_policy.build_pack(schema_version="1", trace_id="trace-gate", turn_id="turn-gate", intent_ref=grounded_intent, candidates=(evidence,))))
        if grounded.plan.route_profile.evidence_token_budget <= 0:
            failures.append("grounded route evidence budget must be non-zero")
        if grounded.plan.suppression.evidence_block_suppressed:
            failures.append("grounded route evidence block must not be suppressed when evidence exists")
        if PromptSectionKind.EVIDENCE_CONTEXT not in {section.kind for section in grounded.plan.sections}:
            failures.append("grounded route must inject evidence section")

        tool_manifest = CapabilityManifest(schema_version="1", capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="tool.calculator"), display_name="Calculator", description="Safe calculator", owner_package="gate", adapter_boundary="gate", permissions=("tool.calculator.call",), input_schema={"type": "object"})
        tool_intent = _intent(IntentKind.CAPABILITY_TOOL)
        tool_policy = adaptive_context_policy_for_route(AdaptivePromptRoute.TOOL_USE)
        tool_candidate = tool_schema_context_candidate(tool_manifest, route=AdaptivePromptRoute.TOOL_USE, risk_level=ToolRiskLevel.LOW, approval_required=False, eligible=True)
        tool_result = assemble_adaptive_prompt_harness(PromptAssemblyRequest(schema_version="1", trace_id="trace-tool-gate", turn_id="turn-tool-gate", intent_ref=tool_intent, context_pack=tool_policy.build_pack(schema_version="1", trace_id="trace-tool-gate", turn_id="turn-tool-gate", intent_ref=tool_intent, candidates=(tool_candidate,))))
        if tool_result.plan.suppression.tool_block_suppressed:
            failures.append("tool route schema block must not be suppressed when eligible tool exists")

        read = classify_governance_action(GovernanceAction(requested_action="search web", capability="web.search", permission=GranularPermission.PUBLIC_READ))
        delete = classify_governance_action(GovernanceAction(requested_action="delete file", capability="file.delete", permission=GranularPermission.WRITE_LOCAL))
        injection = classify_governance_action(GovernanceAction(requested_action="command injection exfiltrate", capability="shell", permission=GranularPermission.EXECUTE_COMMAND))
        if read.decision != GovernanceDecisionType.ALLOW:
            failures.append("read/list/search governance must be allowed")
        if delete.decision != GovernanceDecisionType.APPROVAL_REQUIRED:
            failures.append("write/delete/send/execute governance must require approval")
        if injection.decision != GovernanceDecisionType.HARD_BLOCK:
            failures.append("command injection/exfiltration must hard-block")
        if not delete.safe_projection().reason_codes:
            failures.append("governance decisions must include reason codes")

        proposal = McpAllowlistProposal.propose_add_tool(policy_id="mcp.gate", server_id="local", tool_name="safe_lookup", requested_by="control_plane")
        policy = McpAllowlistPolicy.from_runtime_config(policy_id="mcp.gate", allowed_server_ids=("local",), allowed_tool_names=("safe_lookup",), source="control_plane")
        if not proposal.review_required or proposal.applied_without_review:
            failures.append("MCP allowlist proposals must require review")
        if policy.safe_projection()["policy_source"] == "source_only":
            failures.append("MCP allowlist cannot be hard-coded source-only")

        learning = LearningLoop.default().process((FeedbackEvent.from_user_correction(trace_id="trace-learn-gate", turn_id="turn-learn-gate", correction=UserCorrection(text="Prefer recent evidence", applies_to="answer")),))
        if learning.silent_policy_mutation or learning.silent_skill_mutation:
            failures.append("learning loop cannot silently mutate policy or skills")
        if not learning.memory_write_candidates:
            failures.append("learning loop must create reviewable candidates from correction")

    required_files = (
        ROOT / "packages" / "prompt_harness_runtime" / "adaptive.py",
        ROOT / "packages" / "memory_tree_runtime" / "search.py",
        ROOT / "packages" / "learning_runtime" / "__init__.py",
        ROOT / "packages" / "capability_runtime" / "governance_audit.py",
    )
    for path in required_files:
        if not path.is_file():
            failures.append(f"missing adaptive runtime file: {path.relative_to(ROOT).as_posix()}")

    run_all = (ROOT / "scripts" / "run_all_checks.py").read_text(encoding="utf-8")
    if "check_adaptive_context_learning_governance.py" not in run_all:
        failures.append("scripts/run_all_checks.py must run check_adaptive_context_learning_governance.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS adaptive context learning governance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
