from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.contracts.state_event import AssistantStatusKind


class ProactiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


ProactiveSignal = Literal["dont_ask_again", "say_that_less", "only_when_critical", "say_that_more"]


class TopicPreference(ProactiveModel):
    topic: str = Field(..., min_length=1, max_length=120)
    signal: ProactiveSignal


class ProactivePreferencePolicy(ProactiveModel):
    topic_preferences: tuple[TopicPreference, ...] = ()
    default_min_severity: Literal["critical"] = "critical"
    hidden_background_actions_allowed: Literal[False] = False

    @classmethod
    def default(cls) -> "ProactivePreferencePolicy":
        return cls()

    def apply_signal(self, *, topic: str, signal: ProactiveSignal) -> "ProactivePreferencePolicy":
        kept = tuple(item for item in self.topic_preferences if item.topic != topic)
        return self.model_copy(update={"topic_preferences": kept + (TopicPreference(topic=topic, signal=signal),)})

    def signal_for(self, topic: str) -> ProactiveSignal | None:
        for item in self.topic_preferences:
            if item.topic == topic:
                return item.signal
        return None


class ProactiveDecision(ProactiveModel):
    schema_version: str = "0.1.1-draft"
    trace_id: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1, max_length=120)
    status: Literal["disabled", "suppressed", "proposed", "not_relevant"]
    reason_codes: tuple[str, ...]
    visible_to_user: bool
    approval_required: Literal[True] = True
    action_execution_started: Literal[False] = False
    local_only: Literal[True] = True
    raw_desktop_content_persisted: Literal[False] = False
    raw_screen_persisted: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class ProactiveWorker(ProactiveModel):
    enabled: bool = False
    preferences: ProactivePreferencePolicy = Field(default_factory=ProactivePreferencePolicy.default)

    def evaluate(
        self,
        *,
        trace_id: str,
        topic: str,
        desktop_content: str,
        assistant_status: AssistantStatusKind,
    ) -> ProactiveDecision:
        if not self.enabled:
            return _decision(trace_id, topic, status="disabled", reasons=("proactive.disabled",), visible=False)
        if assistant_status != AssistantStatusKind.IDLE:
            return _decision(trace_id, topic, status="suppressed", reasons=("state.not_idle",), visible=False)
        signal = self.preferences.signal_for(topic)
        if signal == "dont_ask_again":
            return _decision(trace_id, topic, status="suppressed", reasons=("preference.dont_ask_again",), visible=False)
        severity = _severity(desktop_content)
        if signal == "say_that_less" and severity != "critical":
            return _decision(trace_id, topic, status="suppressed", reasons=("preference.say_that_less",), visible=False)
        if signal == "only_when_critical" and severity != "critical":
            return _decision(trace_id, topic, status="suppressed", reasons=("preference.only_when_critical",), visible=False)
        if signal == "say_that_more":
            return _decision(trace_id, topic, status="proposed", reasons=("preference.say_that_more",), visible=True)
        if severity == "critical":
            return _decision(trace_id, topic, status="proposed", reasons=("critical",), visible=True)
        return _decision(trace_id, topic, status="not_relevant", reasons=("severity.below_threshold",), visible=False)


def _decision(
    trace_id: str,
    topic: str,
    *,
    status: Literal["disabled", "suppressed", "proposed", "not_relevant"],
    reasons: tuple[str, ...],
    visible: bool,
) -> ProactiveDecision:
    return ProactiveDecision(
        trace_id=trace_id,
        topic=topic,
        status=status,
        reason_codes=reasons,
        visible_to_user=visible,
    )


def _severity(content: str) -> Literal["critical", "normal"]:
    lowered = content.lower()
    if any(marker in lowered for marker in ("critical", "failed", "failure", "blocked", "exception", "traceback")):
        return "critical"
    return "normal"
