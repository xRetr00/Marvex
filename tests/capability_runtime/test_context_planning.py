from __future__ import annotations

from packages.capability_runtime import (
    CapabilityCompactionPolicy,
    CapabilityContextDeliveryPolicy,
    CapabilityContextPack,
    CapabilityEligibilityDecision,
    CapabilityKind,
    CapabilityLoopGuard,
    CapabilityRef,
    CapabilityStopReason,
    PlanStep,
    TaskDecompositionHint,
    VerificationHook,
)


def test_context_pack_keeps_included_and_excluded_reasons_separate() -> None:
    included = CapabilityEligibilityDecision(
        schema_version="1",
        decision_id="elig-1",
        capability_ref=CapabilityRef(kind=CapabilityKind.SKILL, identifier="skill.summary"),
        eligible=True,
        reason_code="intent_match",
        intent_tags=("summarize",),
    )
    excluded = CapabilityEligibilityDecision(
        schema_version="1",
        decision_id="elig-2",
        capability_ref=CapabilityRef(kind=CapabilityKind.CONNECTOR, identifier="connector.mail"),
        eligible=False,
        reason_code="requires_account_auth",
        intent_tags=("email",),
    )

    pack = CapabilityContextPack(
        schema_version="1",
        trace_id="trace-1",
        turn_id="turn-1",
        delivery_policy=CapabilityContextDeliveryPolicy(max_capabilities=1, include_excluded_reasons=True),
        compaction_policy=CapabilityCompactionPolicy(max_schema_bytes=800, offload_large_schemas=True),
        eligibility_decisions=(included, excluded),
        prompt_contributions=("Use concise summary skill when selected.",),
    )

    delivery = pack.schema_delivery()

    assert [item["identifier"] for item in delivery["included_capabilities"]] == ["skill.summary"]
    assert delivery["excluded_capabilities"] == [
        {"identifier": "connector.mail", "reason_code": "requires_account_auth"}
    ]
    assert delivery["prompt_contributions"] == ["Use concise summary skill when selected."]


def test_loop_guard_and_planning_readiness_are_policy_models_only() -> None:
    guard = CapabilityLoopGuard(
        schema_version="1",
        loop_id="loop-1",
        max_steps=3,
        completed_steps=3,
        stop_reason=CapabilityStopReason.MAX_STEPS_REACHED,
    )
    step = PlanStep(
        schema_version="1",
        plan_ref="plan-1",
        step_id="step-1",
        objective="Verify fake result status.",
        required_capability_refs=(CapabilityRef(kind=CapabilityKind.VERIFIER, identifier="verifier.fake"),),
    )
    hint = TaskDecompositionHint(
        schema_version="1",
        hint_id="hint-1",
        parent_task_ref="task-1",
        suggested_steps=(step,),
        autonomous_execution_allowed=False,
    )
    hook = VerificationHook(
        schema_version="1",
        hook_id="verify-1",
        capability_ref=CapabilityRef(kind=CapabilityKind.VERIFIER, identifier="verifier.fake"),
        required=True,
        reason_code="result_status_check",
    )

    assert guard.should_stop is True
    assert hint.autonomous_execution_allowed is False
    assert hook.safe_projection()["required"] is True
