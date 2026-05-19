# Learning Runtime

`packages.learning_runtime` owns safe feedback and learning candidates. It is inspired by Hermes-style learning loops but remains Marvex-owned and review-gated.

Supported feedback inputs:

- `FeedbackEvent`
- `UserCorrection`
- `AnswerRating`
- `ToolOutcomeFeedback`
- `MemoryUseFeedback`
- `IntentFailureFeedback`
- `RetrievalFailureFeedback`

Produced candidates:

- `MemoryWriteCandidateFromFeedback`
- `SkillImprovementCandidate`
- `PolicyTuningCandidate`
- `PreferenceCandidate`
- memory hotness updates
- route example candidates
- `LearningLoopSummary`
- `SafeLearningProjection`

Rules:

- User corrections can create memory, skill, policy, and preference candidates.
- Successful repeated tool workflows can create skill candidates.
- Failed intent routing can create route example candidates.
- Useful memory feedback can create memory hotness updates.
- No policy or skill is silently mutated.
- Review is required for candidate application.
- Raw feedback is not persisted by default.
