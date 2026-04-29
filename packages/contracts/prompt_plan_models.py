from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from packages.contracts.intent_models import ContractModel, RouteFamily


FUTURE_TOOL_SURFACE_CATEGORIES = (
    "provider_builtin_tools",
    "mcp_server_tools",
    "local_function_tools",
    "desktop_actions",
    "browser_actions",
)


class PromptBlockType(str, Enum):
    IDENTITY = "identity"
    USER_INPUT = "user_input"
    VERIFIED_EVIDENCE = "verified_evidence"
    SELECTED_MEMORY = "selected_memory"
    SELECTED_TOOLS = "selected_tools"
    RESPONSE_CONTRACT = "response_contract"


class PromptBlock(ContractModel):
    block_type: PromptBlockType
    content: str
    reason_code: str = Field(..., min_length=1)
    char_budget: int = Field(..., ge=0)
    included: bool

    @model_validator(mode="after")
    def require_included_content_within_budget(self) -> "PromptBlock":
        if self.included and len(self.content) > self.char_budget:
            raise ValueError("included block content exceeds char_budget")
        return self


class PromptPlan(ContractModel):
    route_family: RouteFamily
    blocks: list[PromptBlock]
    total_budget: int = Field(..., ge=0)
    tool_surface_exposed: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_declarative_budgeted_plan(self) -> "PromptPlan":
        if self.tool_surface_exposed:
            raise ValueError("tool_surface_exposed must stay empty in Task 035")

        budget_used = sum(len(block.content) for block in self.blocks if block.included)
        if budget_used > self.total_budget:
            raise ValueError("included block content exceeds total_budget")
        return self


class PromptAssemblyReport(ContractModel):
    included_blocks: list[PromptBlockType]
    suppressed_blocks: list[PromptBlockType]
    reason_codes: list[str]
    budget_used: int = Field(..., ge=0)
