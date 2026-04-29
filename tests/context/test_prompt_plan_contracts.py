import pytest
from pydantic import ValidationError

from packages.contracts.intent_models import RouteFamily
from packages.contracts.prompt_plan_models import (
    FUTURE_TOOL_SURFACE_CATEGORIES,
    PromptAssemblyReport,
    PromptBlock,
    PromptBlockType,
    PromptPlan,
)


def test_valid_prompt_plan_is_declarative_and_budgeted() -> None:
    block = PromptBlock(
        block_type=PromptBlockType.USER_INPUT,
        content="summarize this",
        reason_code="input.route_scoped",
        char_budget=120,
        included=True,
    )

    plan = PromptPlan(
        route_family=RouteFamily.DIRECT_ANSWER,
        blocks=[block],
        total_budget=200,
    )

    assert plan.route_family == RouteFamily.DIRECT_ANSWER
    assert plan.tool_surface_exposed == []
    assert "prompt" not in plan.model_dump()


def test_rejects_included_block_content_over_budget() -> None:
    with pytest.raises(ValidationError, match="included block content exceeds char_budget"):
        PromptBlock(
            block_type=PromptBlockType.USER_INPUT,
            content="x" * 11,
            reason_code="input.too_large",
            char_budget=10,
            included=True,
        )


def test_rejects_prompt_plan_budget_overflow() -> None:
    block = PromptBlock(
        block_type=PromptBlockType.RESPONSE_CONTRACT,
        content="x" * 20,
        reason_code="response.direct_answer",
        char_budget=20,
        included=True,
    )

    with pytest.raises(ValidationError, match="included block content exceeds total_budget"):
        PromptPlan(
            route_family=RouteFamily.DIRECT_ANSWER,
            blocks=[block],
            total_budget=10,
        )


def test_rejects_non_empty_tool_surface_exposure() -> None:
    with pytest.raises(ValidationError, match="tool_surface_exposed must stay empty"):
        PromptPlan(
            route_family=RouteFamily.GROUNDED_LOOKUP,
            blocks=[],
            total_budget=100,
            tool_surface_exposed=["search"],
        )


def test_future_tool_surface_categories_are_documented_but_not_exposable_yet() -> None:
    assert FUTURE_TOOL_SURFACE_CATEGORIES == (
        "provider_builtin_tools",
        "mcp_server_tools",
        "local_function_tools",
        "desktop_actions",
        "browser_actions",
    )

    with pytest.raises(ValidationError, match="tool_surface_exposed must stay empty"):
        PromptPlan(
            route_family=RouteFamily.GROUNDED_LOOKUP,
            blocks=[],
            total_budget=100,
            tool_surface_exposed=list(FUTURE_TOOL_SURFACE_CATEGORIES),
        )


def test_fails_closed_on_unapproved_block_type() -> None:
    with pytest.raises(ValidationError):
        PromptBlock(
            block_type="hidden_system",
            content="never allowed",
            reason_code="invalid.hidden_system",
            char_budget=20,
            included=True,
        )


def test_assembly_report_records_budget_and_block_reasons() -> None:
    report = PromptAssemblyReport(
        included_blocks=[PromptBlockType.IDENTITY, PromptBlockType.RESPONSE_CONTRACT],
        suppressed_blocks=[PromptBlockType.SELECTED_TOOLS],
        reason_codes=["identity.minimal", "tools.suppressed_task_035"],
        budget_used=42,
    )

    assert report.included_blocks == [
        PromptBlockType.IDENTITY,
        PromptBlockType.RESPONSE_CONTRACT,
    ]
    assert report.suppressed_blocks == [PromptBlockType.SELECTED_TOOLS]
    assert report.budget_used == 42
