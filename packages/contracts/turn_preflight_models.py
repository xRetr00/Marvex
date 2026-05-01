from __future__ import annotations

from pydantic import model_validator

from packages.contracts.decision_pipeline_models import DecisionFinalAction, DecisionPipelineResult
from packages.contracts.intent_models import ContractModel


class TurnPreflightResult(ContractModel):
    enabled: bool
    observed: bool
    final_action: DecisionFinalAction | None
    reason_code: str | None
    decision_pipeline_result: DecisionPipelineResult | None
    blocking_applied: bool

    @model_validator(mode="after")
    def require_observe_only_shape(self) -> "TurnPreflightResult":
        if self.blocking_applied:
            raise ValueError("blocking_applied must remain false")

        if not self.enabled:
            if (
                self.observed
                or self.final_action is not None
                or self.reason_code is not None
                or self.decision_pipeline_result is not None
            ):
                raise ValueError("disabled preflight must not include decision output")
            return self

        if self.observed and (
            self.final_action is None
            or self.reason_code is None
            or self.decision_pipeline_result is None
        ):
            raise ValueError("observed preflight requires decision output")
        return self
