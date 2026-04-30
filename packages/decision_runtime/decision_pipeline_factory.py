from __future__ import annotations

from typing import Any


def create_decision_pipeline(
    pipeline_cls: type,
    router: Any,
    validator: Any,
    policy_gate: Any,
    context_builder: Any,
) -> Any:
    return pipeline_cls(
        router=router,
        validator=validator,
        policy_gate=policy_gate,
        context_builder=context_builder,
    )
