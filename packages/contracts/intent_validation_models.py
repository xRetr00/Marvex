from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from packages.contracts.intent_models import ContractModel, RouteFamily


class IntentRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentValidationResult(ContractModel):
    accepted: bool
    needs_clarification: bool
    risk_level: IntentRiskLevel
    reason_code: str = Field(..., min_length=1)
    corrected_route_family: RouteFamily | None

    @model_validator(mode="after")
    def require_consistent_validation_decision(self) -> "IntentValidationResult":
        if self.accepted and self.needs_clarification:
            raise ValueError("accepted result cannot need clarification")
        if self.accepted and self.risk_level == IntentRiskLevel.HIGH:
            raise ValueError("accepted result cannot be high risk")
        return self
