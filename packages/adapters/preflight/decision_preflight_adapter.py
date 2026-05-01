from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.decision_pipeline_models import DecisionPipelineResult
from packages.contracts.turn_preflight_models import TurnPreflightResult
from packages.ports.decision_pipeline_port import DecisionPipelinePort


@dataclass(frozen=True)
class DecisionPreflightAdapter:
    decision_pipeline: DecisionPipelinePort

    def run(self, input_text: str, enabled: bool) -> TurnPreflightResult:
        if not enabled:
            return TurnPreflightResult(
                enabled=False,
                observed=False,
                final_action=None,
                reason_code=None,
                decision_pipeline_result=None,
                blocking_applied=False,
            )

        decision_result = DecisionPipelineResult.model_validate(
            self.decision_pipeline.run(input_text)
        )
        return TurnPreflightResult(
            enabled=True,
            observed=True,
            final_action=decision_result.final_action,
            reason_code=decision_result.reason_code,
            decision_pipeline_result=decision_result,
            blocking_applied=False,
        )
