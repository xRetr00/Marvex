from __future__ import annotations

from packages.contracts.state_event import AssistantStatusKind
from packages.proactive_runtime import ProactiveDecision, ProactivePreferencePolicy, ProactiveWorker


def test_proactive_worker_is_off_by_default_and_never_executes_actions() -> None:
    worker = ProactiveWorker()
    decision = worker.evaluate(
        trace_id="trace-proactive",
        topic="stuck-test",
        desktop_content="test failure repeated three times",
        assistant_status=AssistantStatusKind.IDLE,
    )

    assert decision.status == "disabled"
    assert decision.action_execution_started is False
    assert decision.approval_required is True
    assert decision.raw_desktop_content_persisted is False


def test_proactive_worker_proposes_visible_critical_initiative_when_enabled() -> None:
    worker = ProactiveWorker(enabled=True, preferences=ProactivePreferencePolicy.default())
    decision = worker.evaluate(
        trace_id="trace-proactive",
        topic="test-failure",
        desktop_content="pytest failed with repeated critical failure",
        assistant_status=AssistantStatusKind.IDLE,
    )

    assert decision.status == "proposed"
    assert decision.visible_to_user is True
    assert decision.approval_required is True
    assert decision.action_execution_started is False
    assert "critical" in decision.reason_codes


def test_proactive_preferences_gate_topics_and_frequency() -> None:
    policy = ProactivePreferencePolicy.default().apply_signal(topic="lint", signal="dont_ask_again")
    worker = ProactiveWorker(enabled=True, preferences=policy)

    decision = worker.evaluate(
        trace_id="trace-proactive",
        topic="lint",
        desktop_content="lint warning",
        assistant_status=AssistantStatusKind.IDLE,
    )

    assert decision.status == "suppressed"
    assert decision.reason_codes == ("preference.dont_ask_again",)


def test_say_more_preference_allows_lower_severity_once_idle() -> None:
    policy = ProactivePreferencePolicy.default().apply_signal(topic="docs", signal="say_that_more")
    worker = ProactiveWorker(enabled=True, preferences=policy)

    decision: ProactiveDecision = worker.evaluate(
        trace_id="trace-proactive",
        topic="docs",
        desktop_content="documentation note",
        assistant_status=AssistantStatusKind.IDLE,
    )

    assert decision.status == "proposed"
    assert decision.reason_codes == ("preference.say_that_more",)
