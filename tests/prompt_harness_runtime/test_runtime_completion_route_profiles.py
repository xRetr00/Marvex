from packages.context_runtime import ContextBudget, ContextCandidate, ContextPack, ContextSourceKind, ContextSourceRef
from packages.intent_runtime import IntentKind, IntentRef
from packages.prompt_harness_runtime import PromptAssemblyRequest, PromptSectionKind, assemble_prompt_harness


def _candidate(kind: ContextSourceKind, identifier: str, text: str, tag: IntentKind, tokens: int = 8) -> ContextCandidate:
    return ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=kind, identifier=identifier),
        text,
        token_estimate=tokens,
        intent_tags=(tag.value,),
    )


def _pack(intent_kind: IntentKind, candidates: tuple[ContextCandidate, ...]) -> ContextPack:
    intent = IntentRef(intent_id=f"intent.{intent_kind.value}", intent_kind=intent_kind)
    return ContextPack(
        schema_version="1",
        trace_id="trace-route-profile",
        turn_id="turn-route-profile",
        intent_ref=intent,
        budget=ContextBudget(max_context_tokens=240, reserved_response_tokens=60),
        included=candidates,
        excluded=(),
        used_context_tokens=sum(candidate.token_estimate for candidate in candidates),
    )


def test_grounded_answer_route_enables_evidence_budget_and_citation_markers() -> None:
    evidence = _candidate(
        ContextSourceKind.WEB_SEARCH_EVIDENCE,
        "web.bundle.browser-use",
        "[web.evidence.1] Browser-use release - https://example.test - Current release evidence.",
        IntentKind.GROUNDED_ANSWER,
    )
    request = PromptAssemblyRequest(
        schema_version="1",
        trace_id="trace-route-profile",
        turn_id="turn-route-profile",
        intent_ref=IntentRef(intent_id="intent.grounded_answer", intent_kind=IntentKind.GROUNDED_ANSWER),
        context_pack=_pack(IntentKind.GROUNDED_ANSWER, (evidence,)),
    )

    result = assemble_prompt_harness(request)

    assert result.plan.route_profile.route == "grounded_answer"
    assert result.plan.route_profile.evidence_token_budget > 0
    assert result.plan.suppression.evidence_block_suppressed is False
    assert result.plan.sections[1].kind == PromptSectionKind.EVIDENCE_CONTEXT
    assert "Use citation markers exactly as supplied" in result.plan.sections[-1].safe_content


def test_memory_tool_skill_and_risk_routes_enable_only_relevant_blocks() -> None:
    cases = (
        (IntentKind.MEMORY, ContextSourceKind.MEMORY_PROJECTION, PromptSectionKind.MEMORY_CONTEXT, "memory_token_budget", "memory_block_suppressed"),
        (IntentKind.CAPABILITY_TOOL, ContextSourceKind.CAPABILITY_SCHEMA, PromptSectionKind.CAPABILITY_SCHEMA, "tool_schema_token_budget", "tool_block_suppressed"),
        (IntentKind.SKILL_NEEDED, ContextSourceKind.SKILL_PROMPT_CONTRIBUTION, PromptSectionKind.SKILL_CONTRIBUTION, "skill_token_budget", "skill_block_suppressed"),
        (IntentKind.RISKY_ACTION, ContextSourceKind.CAPABILITY_SCHEMA, PromptSectionKind.CAPABILITY_SCHEMA, "tool_schema_token_budget", "tool_block_suppressed"),
    )
    for intent_kind, source_kind, section_kind, budget_name, suppression_name in cases:
        candidate = _candidate(source_kind, f"source.{intent_kind.value}", f"Safe context for {intent_kind.value}.", intent_kind)
        result = assemble_prompt_harness(
            PromptAssemblyRequest(
                schema_version="1",
                trace_id=f"trace-{intent_kind.value}",
                turn_id=f"turn-{intent_kind.value}",
                intent_ref=IntentRef(intent_id=f"intent.{intent_kind.value}", intent_kind=intent_kind),
                context_pack=_pack(intent_kind, (candidate,)),
            )
        )

        assert getattr(result.plan.route_profile, budget_name) > 0
        assert getattr(result.plan.suppression, suppression_name) is False
        assert section_kind in [section.kind for section in result.plan.sections]


def test_simple_chat_route_stays_lean() -> None:
    result = assemble_prompt_harness(
        PromptAssemblyRequest(
            schema_version="1",
            trace_id="trace-simple",
            turn_id="turn-simple",
            intent_ref=IntentRef(intent_id="intent.simple", intent_kind=IntentKind.PROVIDER_SIMPLE_CHAT),
            context_pack=_pack(IntentKind.PROVIDER_SIMPLE_CHAT, ()),
        )
    )

    assert result.plan.route_profile.route == "provider_simple_chat"
    assert result.plan.route_profile.evidence_token_budget == 0
    assert result.plan.route_profile.memory_token_budget > 0
    assert result.plan.route_profile.tool_schema_token_budget == 0
    assert [section.kind for section in result.plan.sections] == [PromptSectionKind.SYSTEM_POLICY, PromptSectionKind.RESPONSE_CONTRACT]


def test_route_profiles_leave_room_for_local_context() -> None:
    cases = (
        IntentKind.PROVIDER_SIMPLE_CHAT,
        IntentKind.WEB_SEARCH,
        IntentKind.MEMORY_TREE_NEEDED,
        IntentKind.CAPABILITY_TOOL,
        IntentKind.BROWSER_COMPUTER_USE,
        IntentKind.MCP_NEEDED,
    )
    for intent_kind in cases:
        result = assemble_prompt_harness(
            PromptAssemblyRequest(
                schema_version="1",
                trace_id=f"trace-{intent_kind.value}",
                turn_id=f"turn-{intent_kind.value}",
                intent_ref=IntentRef(intent_id=f"intent.{intent_kind.value}", intent_kind=intent_kind),
                context_pack=_pack(intent_kind, ()),
            )
        )

        assert result.plan.route_profile.total_context_budget >= 6000
        assert result.plan.route_profile.max_context_candidates >= 16
