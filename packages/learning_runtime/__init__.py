from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import AutonomyAction, AutonomyPolicy, PolicyDecisionAuditRecord, ToolRiskLevel, evaluate_autonomy_action
from packages.proactive_runtime import ProactivePreferencePolicy, ProactiveSignal


class LearningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FeedbackSignalKind(str, Enum):
    USER_CORRECTION = "user_correction"
    ANSWER_RATING = "answer_rating"
    TOOL_OUTCOME = "tool_outcome"
    MEMORY_USE = "memory_use"
    INTENT_FAILURE = "intent_failure"
    RETRIEVAL_FAILURE = "retrieval_failure"


class UserCorrection(LearningModel):
    text: str = Field(..., min_length=1, max_length=600)
    applies_to: str = Field(..., min_length=1, max_length=80)


class AnswerRating(LearningModel):
    rating: int = Field(..., ge=1, le=5)
    reason: str = Field(..., min_length=1, max_length=240)


class ToolOutcomeFeedback(LearningModel):
    tool_ref: str
    succeeded: bool
    outcome_reason: str


class MemoryUseFeedback(LearningModel):
    memory_ref: str
    useful: bool
    reason: str


class IntentFailureFeedback(LearningModel):
    input_summary: str
    expected_intent: str
    actual_intent: str


class RetrievalFailureFeedback(LearningModel):
    query_summary: str
    reason: str


FeedbackPayload = Union[UserCorrection, AnswerRating, ToolOutcomeFeedback, MemoryUseFeedback, IntentFailureFeedback, RetrievalFailureFeedback]


class FeedbackEvent(LearningModel):
    trace_id: str
    turn_id: str
    signal_kind: FeedbackSignalKind
    payload: FeedbackPayload
    raw_feedback_persisted: Literal[False] = False

    @classmethod
    def from_user_correction(cls, *, trace_id: str, turn_id: str, correction: UserCorrection) -> "FeedbackEvent":
        return cls(trace_id=trace_id, turn_id=turn_id, signal_kind=FeedbackSignalKind.USER_CORRECTION, payload=correction)


class MemoryWriteCandidateFromFeedback(LearningModel):
    candidate_id: str
    summary: str
    review_required: Literal[True] = True


class SkillImprovementCandidate(LearningModel):
    candidate_id: str
    summary: str
    review_required: Literal[True] = True


class PolicyTuningCandidate(LearningModel):
    candidate_id: str
    summary: str
    review_required: Literal[True] = True


class PreferenceCandidate(LearningModel):
    candidate_id: str
    summary: str
    explicit_user_signal_required: Literal[True] = True
    review_required: Literal[True] = True


class MemoryHotnessUpdate(LearningModel):
    memory_ref: str
    useful: bool
    reason_code: str


class RouteExampleCandidate(LearningModel):
    input_summary: str
    expected_intent: str
    actual_intent: str
    review_required: Literal[True] = True


class SafeLearningProjection(LearningModel):
    feedback_count: int
    memory_candidate_count: int
    skill_candidate_count: int
    policy_candidate_count: int
    preference_candidate_count: int
    silent_policy_mutation: Literal[False] = False
    silent_skill_mutation: Literal[False] = False
    raw_feedback_persisted: Literal[False] = False


class LearningLoopSummary(LearningModel):
    feedback_count: int
    memory_write_candidates: tuple[MemoryWriteCandidateFromFeedback, ...] = ()
    skill_improvement_candidates: tuple[SkillImprovementCandidate, ...] = ()
    policy_tuning_candidates: tuple[PolicyTuningCandidate, ...] = ()
    preference_candidates: tuple[PreferenceCandidate, ...] = ()
    memory_hotness_updates: tuple[MemoryHotnessUpdate, ...] = ()
    route_example_candidates: tuple[RouteExampleCandidate, ...] = ()
    silent_policy_mutation: Literal[False] = False
    silent_skill_mutation: Literal[False] = False

    def safe_projection(self) -> SafeLearningProjection:
        return SafeLearningProjection(
            feedback_count=self.feedback_count,
            memory_candidate_count=len(self.memory_write_candidates),
            skill_candidate_count=len(self.skill_improvement_candidates),
            policy_candidate_count=len(self.policy_tuning_candidates),
            preference_candidate_count=len(self.preference_candidates),
        )


class LearningApplyResult(LearningModel):
    candidate_id: str
    status: Literal["applied", "approval_required", "denied"]
    audit_record: PolicyDecisionAuditRecord
    raw_candidate_payload_persisted: Literal[False] = False


class LearningCandidateStore:
    def __init__(self) -> None:
        self._feedback_events: tuple[FeedbackEvent, ...] = ()
        self._latest_summary: LearningLoopSummary | None = None
        self._applied_candidate_ids: tuple[str, ...] = ()

    @property
    def feedback_events(self) -> tuple[FeedbackEvent, ...]:
        return self._feedback_events

    @property
    def applied_candidate_ids(self) -> tuple[str, ...]:
        return self._applied_candidate_ids

    @property
    def latest_summary(self) -> LearningLoopSummary | None:
        return self._latest_summary

    def record(self, events: tuple[FeedbackEvent, ...], summary: LearningLoopSummary) -> None:
        self._feedback_events = self._feedback_events + events
        self._latest_summary = summary

    def apply(self, candidate_id: str) -> None:
        self._applied_candidate_ids = self._applied_candidate_ids + (candidate_id,)


class ProactivePreferenceStore:
    def __init__(self, policy: ProactivePreferencePolicy | None = None) -> None:
        self._policy = policy or ProactivePreferencePolicy.default()

    @property
    def policy(self) -> ProactivePreferencePolicy:
        return self._policy

    def apply_user_signal(self, *, topic: str, signal: ProactiveSignal) -> ProactivePreferencePolicy:
        self._policy = self._policy.apply_signal(topic=topic, signal=signal)
        return self._policy

    def safe_projection(self) -> dict[str, object]:
        return {
            "topic_preference_count": len(self._policy.topic_preferences),
            "hidden_background_actions_allowed": False,
            "raw_feedback_persisted": False,
            "raw_payload_persisted": False,
        }


class LearningPipelineRunner:
    def __init__(self, *, store: LearningCandidateStore, autonomy_policy: AutonomyPolicy, loop: LearningLoop | None = None) -> None:
        self._store = store
        self._policy = autonomy_policy
        self._loop = loop or LearningLoop.default()

    def ingest_and_run(self, events: tuple[FeedbackEvent, ...]) -> LearningLoopSummary:
        summary = self._loop.process(events)
        self._store.record(events, summary)
        return summary

    def ingest_feedback_payload(self, payload: dict[str, object]) -> LearningLoopSummary:
        event = FeedbackEvent.model_validate(payload)
        return self.ingest_and_run((event,))

    def apply_candidate(self, candidate_id: str) -> LearningApplyResult:
        audit = evaluate_autonomy_action(
            self._policy,
            AutonomyAction(action=f"apply learning candidate {candidate_id}", resource_type="learning_candidate", capability="learning_mutation", risk_level=ToolRiskLevel.MEDIUM),
        )
        if audit.decision.value == "allow":
            self._store.apply(candidate_id)
            status: Literal["applied", "approval_required", "denied"] = "applied"
        elif audit.decision.value == "approval_required":
            status = "approval_required"
        else:
            status = "denied"
        return LearningApplyResult(candidate_id=candidate_id, status=status, audit_record=audit)


class LearningLoop:
    @classmethod
    def default(cls) -> "LearningLoop":
        return cls()

    def process(self, events: tuple[FeedbackEvent, ...]) -> LearningLoopSummary:
        memory: list[MemoryWriteCandidateFromFeedback] = []
        skills: list[SkillImprovementCandidate] = []
        policies: list[PolicyTuningCandidate] = []
        prefs: list[PreferenceCandidate] = []
        hotness: list[MemoryHotnessUpdate] = []
        routes: list[RouteExampleCandidate] = []
        for index, event in enumerate(events, start=1):
            payload = event.payload
            if isinstance(payload, UserCorrection):
                memory.append(MemoryWriteCandidateFromFeedback(candidate_id=f"memory.feedback.{index}", summary=payload.text[:200]))
                skills.append(SkillImprovementCandidate(candidate_id=f"skill.feedback.{index}", summary=f"Review skill candidate from correction about {payload.applies_to}"))
                policies.append(PolicyTuningCandidate(candidate_id=f"policy.feedback.{index}", summary="Review policy tuning from explicit correction"))
                prefs.append(PreferenceCandidate(candidate_id=f"preference.feedback.{index}", summary=payload.text[:200]))
            elif isinstance(payload, ToolOutcomeFeedback) and payload.succeeded:
                skills.append(SkillImprovementCandidate(candidate_id=f"skill.tool.{index}", summary=f"Successful workflow candidate for {payload.tool_ref}"))
            elif isinstance(payload, MemoryUseFeedback):
                hotness.append(MemoryHotnessUpdate(memory_ref=payload.memory_ref, useful=payload.useful, reason_code="memory.feedback.useful" if payload.useful else "memory.feedback.not_useful"))
            elif isinstance(payload, IntentFailureFeedback):
                routes.append(RouteExampleCandidate(input_summary=payload.input_summary, expected_intent=payload.expected_intent, actual_intent=payload.actual_intent))
                policies.append(PolicyTuningCandidate(candidate_id=f"policy.intent.{index}", summary="Review routing policy candidate from intent failure"))
            elif isinstance(payload, AnswerRating) and payload.rating <= 2:
                policies.append(PolicyTuningCandidate(candidate_id=f"policy.rating.{index}", summary=f"Review answer quality issue: {payload.reason}"))
            elif isinstance(payload, RetrievalFailureFeedback):
                policies.append(PolicyTuningCandidate(candidate_id=f"policy.retrieval.{index}", summary=f"Review retrieval fallback issue: {payload.reason}"))
        return LearningLoopSummary(
            feedback_count=len(events),
            memory_write_candidates=tuple(memory),
            skill_improvement_candidates=tuple(skills),
            policy_tuning_candidates=tuple(policies),
            preference_candidates=tuple(prefs),
            memory_hotness_updates=tuple(hotness),
            route_example_candidates=tuple(routes),
        )
