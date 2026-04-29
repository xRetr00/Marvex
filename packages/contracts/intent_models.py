from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteFamily(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    GROUNDED_LOOKUP = "grounded_lookup"
    LOCAL_STATE_INSPECTION = "local_state_inspection"
    CLARIFY = "clarify"


class IntentDecision(ContractModel):
    route_family: RouteFamily
    confidence: float = Field(..., ge=0.0, le=1.0)
    ambiguity_flag: bool


class PolicyDecision(ContractModel):
    allow: bool
    clarify: bool
    deny: bool
    reason_code: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_exactly_one_decision(self) -> "PolicyDecision":
        selected = sum([self.allow, self.clarify, self.deny])
        if selected != 1:
            raise ValueError("exactly one policy decision flag must be true")
        return self
