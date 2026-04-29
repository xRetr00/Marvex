from packages.adapters.context.context_builder import ContextBuilder
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.prompt_plan_models import PromptBlockType


def intent(route_family: RouteFamily) -> IntentDecision:
    return IntentDecision(
        route_family=route_family,
        confidence=0.88,
        ambiguity_flag=False,
    )


def policy_allow() -> PolicyDecision:
    return PolicyDecision(
        allow=True,
        clarify=False,
        deny=False,
        reason_code="policy.allowed",
    )


def block_map(plan):
    return {block.block_type: block for block in plan.blocks}


def test_long_user_input_is_suppressed_instead_of_expanding_budget() -> None:
    builder = ContextBuilder(user_input_budget=80)

    plan, report = builder.build_prompt_plan(
        "x" * 200,
        intent(RouteFamily.DIRECT_ANSWER),
        policy_allow(),
    )

    user_block = block_map(plan)[PromptBlockType.USER_INPUT]
    assert user_block.included is False
    assert user_block.content == ""
    assert user_block.reason_code == "input.suppressed_over_budget"
    assert PromptBlockType.USER_INPUT in report.suppressed_blocks


def test_budget_used_never_exceeds_total_budget() -> None:
    builder = ContextBuilder(total_budget=180, user_input_budget=120)

    plan, report = builder.build_prompt_plan(
        "x" * 100,
        intent(RouteFamily.GROUNDED_LOOKUP),
        policy_allow(),
    )

    assert report.budget_used <= plan.total_budget
    assert sum(len(block.content) for block in plan.blocks if block.included) == report.budget_used


def test_over_budget_response_contract_is_suppressed_instead_of_raising() -> None:
    builder = ContextBuilder(response_contract_budget=10)

    plan, report = builder.build_prompt_plan(
        "short",
        intent(RouteFamily.GROUNDED_LOOKUP),
        policy_allow(),
    )

    response_block = block_map(plan)[PromptBlockType.RESPONSE_CONTRACT]
    assert response_block.included is False
    assert response_block.content == ""
    assert response_block.reason_code == "response.grounded_lookup.suppressed_block_budget"
    assert PromptBlockType.RESPONSE_CONTRACT in report.suppressed_blocks


def test_evidence_memory_and_tool_blocks_are_suppressed_placeholders_by_default() -> None:
    builder = ContextBuilder()

    plan, report = builder.build_prompt_plan(
        "answer this",
        intent(RouteFamily.DIRECT_ANSWER),
        policy_allow(),
    )

    blocks = block_map(plan)
    for block_type in [
        PromptBlockType.VERIFIED_EVIDENCE,
        PromptBlockType.SELECTED_MEMORY,
        PromptBlockType.SELECTED_TOOLS,
    ]:
        assert blocks[block_type].included is False
        assert blocks[block_type].content == ""
        assert block_type in report.suppressed_blocks

    assert plan.tool_surface_exposed == []
