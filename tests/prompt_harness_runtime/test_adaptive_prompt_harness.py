from __future__ import annotations

from packages.capability_runtime import CapabilityKind, CapabilityManifest, CapabilityRef, ToolRiskLevel
from packages.context_runtime import ContextCandidate, ContextSourceKind, ContextSourceRef, ContextSourceTrustLevel
from packages.intent_runtime import IntentKind, IntentRef
from packages.prompt_harness_runtime.adaptive import (
    AdaptivePromptRoute,
    adaptive_context_policy_for_route,
    assemble_adaptive_prompt_harness,
    tool_schema_context_candidate,
)
from packages.prompt_harness_runtime import PromptAssemblyRequest, PromptSectionKind


def _intent(kind: IntentKind) -> IntentRef:
    return IntentRef(intent_id=f"intent.{kind.value}", intent_kind=kind)


def _candidate(kind: ContextSourceKind, identifier: str, summary: str, tags: tuple[str, ...], tokens: int = 40) -> ContextCandidate:
    return ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=kind, identifier=identifier),
        summary,
        token_estimate=tokens,
        intent_tags=tags,
        trust_level=ContextSourceTrustLevel.UNTRUSTED_SUMMARY if "evidence" in kind.value else ContextSourceTrustLevel.INTERNAL_SAFE_PROJECTION,
    )


def test_grounded_lookup_injects_evidence_with_nonzero_budget_and_citation_guidance() -> None:
    intent_ref = _intent(IntentKind.GROUNDED_ANSWER)
    policy = adaptive_context_policy_for_route(AdaptivePromptRoute.GROUNDED_LOOKUP)
    evidence = _candidate(
        ContextSourceKind.WEB_SEARCH_EVIDENCE,
        "web.evidence.browser-use",
        "[web.evidence.1] Browser-use 0.11.13 release notes - https://example.test/browser-use - safe snippet",
        (IntentKind.GROUNDED_ANSWER.value, IntentKind.WEB_SEARCH.value),
    )

    result = assemble_adaptive_prompt_harness(
        PromptAssemblyRequest(schema_version="1", trace_id="trace-adaptive", turn_id="turn-adaptive", intent_ref=intent_ref, context_pack=policy.build_pack(schema_version="1", trace_id="trace-adaptive", turn_id="turn-adaptive", intent_ref=intent_ref, candidates=(evidence,)))
    )

    kinds = [section.kind for section in result.plan.sections]
    assert result.plan.route_profile.evidence_token_budget > 0
    assert PromptSectionKind.EVIDENCE_CONTEXT in kinds
    assert kinds.index(PromptSectionKind.EVIDENCE_CONTEXT) < kinds.index(PromptSectionKind.RESPONSE_CONTRACT)
    assert any("Cite only provided evidence refs" in section.safe_content for section in result.plan.sections)
    assert result.plan.suppression.evidence_block_suppressed is False


def test_memory_query_enables_memory_block_and_prioritizes_memory_evidence() -> None:
    intent_ref = _intent(IntentKind.MEMORY_TREE_NEEDED)
    policy = adaptive_context_policy_for_route(AdaptivePromptRoute.MEMORY_QUERY)
    memory = _candidate(ContextSourceKind.MEMORY_PROJECTION, "memory.node.marvex", "[memory.evidence.chunk-1] Marvex memory tree evidence summary", (IntentKind.MEMORY_TREE_NEEDED.value,), tokens=55)

    result = assemble_adaptive_prompt_harness(
        PromptAssemblyRequest(schema_version="1", trace_id="trace-memory", turn_id="turn-memory", intent_ref=intent_ref, context_pack=policy.build_pack(schema_version="1", trace_id="trace-memory", turn_id="turn-memory", intent_ref=intent_ref, candidates=(memory,)))
    )

    kinds = [section.kind for section in result.plan.sections]
    assert result.plan.route_profile.memory_token_budget >= 300
    assert PromptSectionKind.MEMORY_CONTEXT in kinds
    assert kinds.index(PromptSectionKind.MEMORY_CONTEXT) < kinds.index(PromptSectionKind.RESPONSE_CONTRACT)
    assert result.plan.suppression.memory_block_suppressed is False


def test_tool_route_injects_only_eligible_tool_schema_without_policy_metadata() -> None:
    calculator = CapabilityManifest(
        schema_version="1",
        capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="tool.calculator"),
        display_name="Calculator",
        description="Arithmetic calculator",
        owner_package="packages.adapters.capabilities.builtins",
        adapter_boundary="builtins",
        permissions=("tool.calculator.call",),
        input_schema={"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
    )
    browser = CapabilityManifest(
        schema_version="1",
        capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="tool.browser.click"),
        display_name="Browser Click",
        description="Browser click",
        owner_package="packages.adapters.capabilities.browser",
        adapter_boundary="browser",
        permissions=("browser.click",),
        input_schema={"type": "object"},
    )
    calculator_candidate = tool_schema_context_candidate(calculator, route=AdaptivePromptRoute.TOOL_USE, risk_level=ToolRiskLevel.LOW, approval_required=False, eligible=True)
    browser_candidate = tool_schema_context_candidate(browser, route=AdaptivePromptRoute.TOOL_USE, risk_level=ToolRiskLevel.HIGH, approval_required=True, eligible=False)
    intent_ref = _intent(IntentKind.CAPABILITY_TOOL)
    policy = adaptive_context_policy_for_route(AdaptivePromptRoute.TOOL_USE)

    result = assemble_adaptive_prompt_harness(
        PromptAssemblyRequest(schema_version="1", trace_id="trace-tool", turn_id="turn-tool", intent_ref=intent_ref, context_pack=policy.build_pack(schema_version="1", trace_id="trace-tool", turn_id="turn-tool", intent_ref=intent_ref, candidates=(calculator_candidate, browser_candidate)))
    )

    schema_sections = [section for section in result.plan.sections if section.kind == PromptSectionKind.CAPABILITY_SCHEMA]
    assert len(schema_sections) == 1
    assert "tool.calculator" in schema_sections[0].safe_content
    assert "risk=" not in schema_sections[0].safe_content
    assert "approval_required=" not in schema_sections[0].safe_content
    assert "tool.browser.click" not in "\n".join(section.safe_content for section in result.plan.sections)
    assert all(section.kind != PromptSectionKind.APPROVAL_STATE for section in result.plan.sections)
    assert result.plan.suppression.tool_block_suppressed is False


def test_clarification_route_keeps_minimal_context_and_suppresses_unneeded_blocks() -> None:
    intent_ref = _intent(IntentKind.CLARIFICATION)
    policy = adaptive_context_policy_for_route(AdaptivePromptRoute.CLARIFICATION)
    evidence = _candidate(ContextSourceKind.WEB_SEARCH_EVIDENCE, "web.evidence.extra", "irrelevant evidence", (IntentKind.GROUNDED_ANSWER.value,))

    result = assemble_adaptive_prompt_harness(
        PromptAssemblyRequest(schema_version="1", trace_id="trace-clarify", turn_id="turn-clarify", intent_ref=intent_ref, context_pack=policy.build_pack(schema_version="1", trace_id="trace-clarify", turn_id="turn-clarify", intent_ref=intent_ref, candidates=(evidence,)))
    )

    assert all(section.kind != PromptSectionKind.EVIDENCE_CONTEXT for section in result.plan.sections)
    assert result.plan.route_profile.evidence_token_budget == 0
    assert result.plan.suppression.evidence_block_suppressed is True
