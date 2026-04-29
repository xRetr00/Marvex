from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


# Pydantic AI and Outlines are compared in docs/library-decisions/policy_engine.md.
# This spike intentionally uses only approved Pydantic validation and adds no
# runtime dependency on either framework.


RouteFamily = Literal[
    "direct_answer",
    "grounded_lookup",
    "local_state_inspection",
    "clarify",
]


class ToyIntentValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_family: RouteFamily
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_clarification: bool
    rationale: str = Field(..., min_length=1, max_length=240)

    @model_validator(mode="after")
    def clarify_low_confidence(self) -> "ToyIntentValidation":
        if self.confidence < 0.45 and not self.needs_clarification:
            raise ValueError("low confidence intent decisions must ask for clarification")
        if self.needs_clarification and self.route_family != "clarify":
            raise ValueError("clarification decisions must use the clarify route family")
        return self


def test_valid_structured_intent_json_shape() -> None:
    decision = ToyIntentValidation.model_validate(
        {
            "route_family": "grounded_lookup",
            "confidence": 0.83,
            "needs_clarification": False,
            "rationale": "freshness sensitive request needs evidence",
        }
    )

    assert decision.route_family == "grounded_lookup"
    assert decision.confidence == 0.83


def test_invalid_extra_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToyIntentValidation.model_validate(
            {
                "route_family": "direct_answer",
                "confidence": 0.72,
                "needs_clarification": False,
                "rationale": "stable general answer",
                "tool_names": ["web_search"],
            }
        )


def test_invalid_route_family_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToyIntentValidation.model_validate(
            {
                "route_family": "agent_runtime",
                "confidence": 0.80,
                "needs_clarification": False,
                "rationale": "invalid framework route",
            }
        )


def test_ambiguous_low_confidence_must_route_to_clarify() -> None:
    decision = ToyIntentValidation.model_validate(
        {
            "route_family": "clarify",
            "confidence": 0.31,
            "needs_clarification": True,
            "rationale": "ambiguous referent",
        }
    )

    assert decision.route_family == "clarify"
    assert decision.needs_clarification is True


def test_low_confidence_non_clarification_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToyIntentValidation.model_validate(
            {
                "route_family": "local_state_inspection",
                "confidence": 0.31,
                "needs_clarification": False,
                "rationale": "ambiguous but incorrectly executable",
            }
        )
