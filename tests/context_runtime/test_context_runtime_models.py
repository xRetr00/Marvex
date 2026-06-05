from packages.capability_runtime import CapabilityEligibilityDecision, CapabilityKind, CapabilityRef
from packages.context_runtime import (
    ContextBudget,
    ContextCandidate,
    ContextDeliveryPolicy,
    ContextEligibilityDecision,
    ContextSourceKind,
    ContextSourceRef,
    ContextSourceTrustLevel,
    build_context_pack,
)
from packages.intent_runtime import IntentKind, IntentRef


def test_context_runtime_selects_only_eligible_context_under_budget() -> None:
    intent_ref = IntentRef(intent_id="intent.tool", intent_kind=IntentKind.CAPABILITY_TOOL)
    candidates = (
        ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier="input.1"), "User asks for calculation", token_estimate=4, intent_tags=("capability_tool",)),
        ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier="memory.1"), "Long-term preference", token_estimate=8, intent_tags=("memory",)),
        ContextCandidate.from_safe_summary(ContextSourceRef(kind=ContextSourceKind.CAPABILITY_SCHEMA, identifier="builtin.calculator"), "calculator schema", token_estimate=6, intent_tags=("capability_tool",)),
    )

    pack = build_context_pack(
        schema_version="1",
        trace_id="trace-1",
        turn_id="turn-1",
        intent_ref=intent_ref,
        candidates=candidates,
        budget=ContextBudget(max_context_tokens=12, reserved_response_tokens=20),
        policy=ContextDeliveryPolicy(max_candidates=4, allowed_source_kinds=(ContextSourceKind.USER_INPUT_SUMMARY, ContextSourceKind.CAPABILITY_SCHEMA), include_excluded_reasons=True),
    )

    assert [item.source_ref.identifier for item in pack.included] == ["input.1", "builtin.calculator"]
    assert len(pack.excluded) == 1
    assert pack.all_context_injected is False
    assert pack.safe_projection().raw_context_persisted is False


def test_context_runtime_excludes_browser_tools_by_default_until_intent_allows() -> None:
    intent_ref = IntentRef(intent_id="intent.chat", intent_kind=IntentKind.PROVIDER_SIMPLE_CHAT)
    browser_tool = ContextCandidate.from_capability_schema(
        CapabilityEligibilityDecision(schema_version="1", decision_id="elig-1", capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="browser.click"), eligible=True, reason_code="eligible.browser", intent_tags=("browser_computer_use",)),
        token_estimate=5,
        trust_level=ContextSourceTrustLevel.INTERNAL_SAFE_PROJECTION,
    )

    pack = build_context_pack(
        schema_version="1",
        trace_id="trace-2",
        turn_id="turn-2",
        intent_ref=intent_ref,
        candidates=(browser_tool,),
        budget=ContextBudget(max_context_tokens=30, reserved_response_tokens=20),
        policy=ContextDeliveryPolicy(max_candidates=4, allowed_source_kinds=(ContextSourceKind.CAPABILITY_SCHEMA,), include_excluded_reasons=True, browser_computer_default_excluded=True),
    )

    assert pack.included == ()
    assert pack.excluded[0].reason_code == "excluded.intent_mismatch"
    assert "browser.click" in pack.safe_projection().model_dump_json()


def test_context_runtime_accepts_large_model_context_windows() -> None:
    intent_ref = IntentRef(intent_id="intent.large", intent_kind=IntentKind.PROVIDER_SIMPLE_CHAT)
    candidate = ContextCandidate.from_safe_summary(
        ContextSourceRef(kind=ContextSourceKind.USER_INPUT_SUMMARY, identifier="input.large"),
        "Large context model request",
        token_estimate=250_000,
    )

    pack = build_context_pack(
        schema_version="1",
        trace_id="trace-large-context",
        turn_id="turn-large-context",
        intent_ref=intent_ref,
        candidates=(candidate,),
        budget=ContextBudget(max_context_tokens=1_047_576, reserved_response_tokens=128_000),
        policy=ContextDeliveryPolicy(max_candidates=4, allowed_source_kinds=(ContextSourceKind.USER_INPUT_SUMMARY,)),
    )

    assert pack.used_context_tokens == 250_000
    assert pack.safe_projection().max_context_tokens == 1_047_576
