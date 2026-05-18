from packages.intent_runtime import (
    ClarificationNeededDecision,
    IntentClassificationRequest,
    IntentKind,
    IntentRiskSignal,
    classify_intent,
)


def test_intent_runtime_classifies_capability_memory_and_control_intents_safely() -> None:
    capability = classify_intent(IntentClassificationRequest(schema_version="1", trace_id="trace-1", turn_id="turn-1", user_input_summary="Use the calculator tool for 2+2"))
    memory = classify_intent(IntentClassificationRequest(schema_version="1", trace_id="trace-2", turn_id="turn-2", user_input_summary="Remember my preference for short answers"))
    control = classify_intent(IntentClassificationRequest(schema_version="1", trace_id="trace-3", turn_id="turn-3", user_input_summary="Open the control plane settings"))

    assert capability.selected_intent.intent_kind == IntentKind.CAPABILITY_TOOL
    assert memory.selected_intent.intent_kind == IntentKind.MEMORY
    assert control.selected_intent.intent_kind == IntentKind.SETTINGS_CONTROL_PLANE
    assert capability.safe_projection().raw_input_persisted is False
    assert "2+2" not in capability.safe_projection().model_dump_json()


def test_intent_runtime_flags_browser_computer_and_unsafe_intents_without_execution() -> None:
    result = classify_intent(IntentClassificationRequest(schema_version="1", trace_id="trace-4", turn_id="turn-4", user_input_summary="Click the checkout button in the browser"))

    assert result.selected_intent.intent_kind == IntentKind.BROWSER_COMPUTER_USE
    assert result.risk_signal == IntentRiskSignal.RISKY_ACTION_REQUESTED
    assert result.route_decision.policy_owner == "packages.capability_runtime"
    assert result.route_decision.execution_allowed is False


def test_low_confidence_intent_requires_clarification() -> None:
    result = classify_intent(IntentClassificationRequest(schema_version="1", trace_id="trace-5", turn_id="turn-5", user_input_summary="that thing from before"))

    assert result.selected_intent.intent_kind == IntentKind.CLARIFICATION
    assert result.clarification == ClarificationNeededDecision.NEEDED
    assert result.ambiguity_signal.ambiguous is True
    assert result.route_decision.execution_allowed is False
