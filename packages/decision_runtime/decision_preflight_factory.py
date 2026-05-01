from __future__ import annotations

from packages.adapters.preflight.decision_preflight_adapter import DecisionPreflightAdapter
from packages.ports.decision_pipeline_port import DecisionPipelinePort


def create_turn_preflight(decision_pipeline: DecisionPipelinePort) -> DecisionPreflightAdapter:
    return DecisionPreflightAdapter(decision_pipeline=decision_pipeline)
