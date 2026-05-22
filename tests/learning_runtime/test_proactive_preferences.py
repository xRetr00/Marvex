from __future__ import annotations

from packages.learning_runtime import ProactivePreferenceStore


def test_learning_runtime_applies_user_mutable_proactive_preferences() -> None:
    store = ProactivePreferenceStore()

    policy = store.apply_user_signal(topic="build-failures", signal="only_when_critical")

    assert policy.signal_for("build-failures") == "only_when_critical"
    assert store.safe_projection()["raw_feedback_persisted"] is False
    assert store.safe_projection()["topic_preference_count"] == 1
