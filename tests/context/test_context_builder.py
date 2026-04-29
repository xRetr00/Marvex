from packages.adapters.context.context_builder import ContextBuilder
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.prompt_plan_models import PromptBlockType


def intent(route_family: RouteFamily, confidence: float = 0.82, ambiguous: bool = False) -> IntentDecision:
    return IntentDecision(
        route_family=route_family,
        confidence=confidence,
        ambiguity_flag=ambiguous,
    )


def policy_allow() -> PolicyDecision:
    return PolicyDecision(
        allow=True,
        clarify=False,
        deny=False,
        reason_code="policy.allowed",
    )


def policy_clarify() -> PolicyDecision:
    return PolicyDecision(
        allow=False,
        clarify=True,
        deny=False,
        reason_code="policy.clarify_ambiguous_route",
    )


def block_map(plan):
    return {block.block_type: block for block in plan.blocks}


def test_direct_answer_plan_includes_minimal_identity_user_input_and_response_contract() -> None:
    builder = ContextBuilder()

    plan, report = builder.build_prompt_plan(
        "Explain the current repository state.",
        intent(RouteFamily.DIRECT_ANSWER),
        policy_allow(),
    )

    blocks = block_map(plan)
    assert plan.route_family == RouteFamily.DIRECT_ANSWER
    assert blocks[PromptBlockType.IDENTITY].included is True
    assert blocks[PromptBlockType.USER_INPUT].included is True
    assert blocks[PromptBlockType.RESPONSE_CONTRACT].included is True
    assert blocks[PromptBlockType.SELECTED_TOOLS].included is False
    assert plan.tool_surface_exposed == []
    assert report.included_blocks == [
        PromptBlockType.IDENTITY,
        PromptBlockType.USER_INPUT,
        PromptBlockType.RESPONSE_CONTRACT,
    ]


def test_clarify_policy_retains_only_redacted_clarification_evidence() -> None:
    builder = ContextBuilder()
    raw_input = "x" * 400

    plan, report = builder.build_prompt_plan(
        raw_input,
        intent(RouteFamily.CLARIFY, confidence=0.31, ambiguous=True),
        policy_clarify(),
    )

    user_block = block_map(plan)[PromptBlockType.USER_INPUT]
    assert plan.route_family == RouteFamily.CLARIFY
    assert user_block.included is True
    assert user_block.content != raw_input
    assert user_block.content.endswith("[redacted]")
    assert len(user_block.content) <= user_block.char_budget
    assert PromptBlockType.USER_INPUT in report.included_blocks


def test_allow_policy_keeps_user_input_only_inside_budgeted_block() -> None:
    builder = ContextBuilder()

    plan, _ = builder.build_prompt_plan(
        "short input",
        intent(RouteFamily.GROUNDED_LOOKUP),
        policy_allow(),
    )

    user_block = block_map(plan)[PromptBlockType.USER_INPUT]
    assert user_block.included is True
    assert user_block.content == "short input"
    assert len(user_block.content) <= user_block.char_budget
    assert user_block.reason_code == "input.budgeted_user_input"


def test_route_specific_response_contracts_do_not_render_global_prompt() -> None:
    builder = ContextBuilder()

    local_plan, _ = builder.build_prompt_plan(
        "inspect local state",
        intent(RouteFamily.LOCAL_STATE_INSPECTION),
        policy_allow(),
    )
    lookup_plan, _ = builder.build_prompt_plan(
        "look up current docs",
        intent(RouteFamily.GROUNDED_LOOKUP),
        policy_allow(),
    )

    local_contract = block_map(local_plan)[PromptBlockType.RESPONSE_CONTRACT]
    lookup_contract = block_map(lookup_plan)[PromptBlockType.RESPONSE_CONTRACT]
    assert local_contract.reason_code == "response.local_state_inspection"
    assert lookup_contract.reason_code == "response.grounded_lookup"
    assert local_contract.content != lookup_contract.content
    assert "tool catalog" not in local_contract.content.lower()
    assert "tool catalog" not in lookup_contract.content.lower()
