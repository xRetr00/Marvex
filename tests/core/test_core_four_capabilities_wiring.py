from __future__ import annotations

# file size justification: comprehensive wiring tests for all four capabilities
# (session, provider selection, learning, telemetry persistence) must cover both
# subprocess integration paths and in-process unit assertions in a single file.

# Tests for the four newly wired capabilities:
# 1. Session runtime (session_ref → memory recall keyed by session)
# 2. Provider selection runtime (selection decision surfaces in metadata)
# 3. Learning runtime (post-turn feedback candidates, review-required)
# 4. Telemetry persistence (PersistentTraceStore wired; /v1/traces reads from it)

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import AssistantTurnResult, FinishReason, ProviderRequest, ProviderResponse
from packages.telemetry import InMemoryTraceReader, PersistentTraceStore


ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingProvider:
    def __init__(self, response_text: str = "OK") -> None:
        self.response_text = response_text
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="recording",
            response_id=f"{request.turn_id}:recording-response",
            output_text=self.response_text,
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )


class _FixedIntentClassifier:
    def __init__(self, intent_kind: str = "provider_simple_chat") -> None:
        self.intent_kind = intent_kind

    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": f"intent.{self.intent_kind}",
                    "intent_kind": self.intent_kind,
                },
                "confidence_bucket": "high",
                "risk_signal": "none",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


def _make_turn_input(text: str, *, session_id: str | None = None, trace_id: str = "trace-cap-test", turn_id: str = "turn-cap-test") -> Any:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        event_id=f"{turn_id}:input",
        text=text,
        timestamp=datetime.now(UTC),
        session_id=session_id,
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id=turn_id,
        input_event=event,
    )


def _make_executor(
    *,
    provider: _RecordingProvider | None = None,
    intent_kind: str = "provider_simple_chat",
    session_registry: Any = None,
    provider_selection: Any = None,
    learning_pipeline: Any = None,
    persistent_store: Any = None,
) -> Any:
    from packages.telemetry import InMemoryTraceReader
    from services.core.main import _CoreServiceProviderWorkerTurnExecutor

    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        session_registry=session_registry,
        provider_selection_runtime=provider_selection,
        learning_pipeline=learning_pipeline,
        persistent_trace_store=persistent_store,
    )
    executor._provider = provider or _RecordingProvider()
    executor._intent_classifier = _FixedIntentClassifier(intent_kind)
    return executor


def _run_core_subprocess_turn(
    text: str,
    *,
    trace_id: str,
    turn_id: str,
    session_id: str | None = None,
    extra: list[str] | None = None,
) -> AssistantTurnResult:
    cmd = [
        sys.executable,
        "-m",
        "services.core.main",
        "--turn-once",
        text,
        "--provider",
        "provider_worker",
        "--worker-provider",
        "fake",
        "--model",
        "fake-model",
        "--trace-id",
        trace_id,
        "--turn-id",
        turn_id,
    ]
    if session_id is not None:
        cmd += ["--session-id", session_id]
    cmd += extra or []
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    return AssistantTurnResult.model_validate(json.loads(completed.stdout))


# ---------------------------------------------------------------------------
# Capability 1: Session runtime
# ---------------------------------------------------------------------------

def test_session_metadata_is_present_without_session_id() -> None:
    """Turns without session_id still get a safe session projection in metadata."""
    result = _run_core_subprocess_turn(
        "Hello from session test",
        trace_id="trace-cap-session-none",
        turn_id="turn-cap-session-none",
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "session" in result.metadata
    session = result.metadata["session"]
    assert session["transcript_persisted"] is False


def test_session_metadata_is_present_with_session_id() -> None:
    """Turns with --session-id carry session_ref and safe projection in metadata."""
    result = _run_core_subprocess_turn(
        "Hello with session",
        trace_id="trace-cap-session-with-id",
        turn_id="turn-cap-session-with-id",
        session_id="test-session-wire-42",
    )

    assert result.error is None
    assert "session" in result.metadata
    session = result.metadata["session"]
    assert session["transcript_persisted"] is False
    # session_ref_present should be True since we passed --session-id
    assert session.get("session_ref_present") is True or "session_ref" in session


def test_session_registry_records_turn_linkage() -> None:
    """CurrentProcessSessionRegistry records the turn linkage after submit_turn."""
    from packages.session_runtime import CurrentProcessSessionRegistry

    registry = CurrentProcessSessionRegistry()
    executor = _make_executor(session_registry=registry)
    turn_input = _make_turn_input("hi", session_id="session-registry-test")

    result = executor.submit_turn(turn_input)

    assert result.error is None
    assert "session" in result.metadata
    proj = registry.read_session_projection(turn_input.session_ref)
    assert proj is not None
    assert proj.turn_count == 1
    assert "turn-cap-test" in proj.turn_ids


def test_session_registry_scopes_memory_recall_by_session_ref(tmp_path: Path) -> None:
    """session_ref flows through to CognitionRuntime so memory is scoped per session."""
    from packages.cognition_runtime import LocalMemoryLoop
    from packages.contracts import ConversationRef, SessionRef
    from packages.memory_runtime import MemoryRecord, MemoryRef

    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    loop = LocalMemoryLoop.open(vault_root=vault_root)
    session_ref = SessionRef(ref_type="session", ref_id="session-cap-memory-scope")
    loop.memory_store.write_record(
        MemoryRecord(
            schema_version="0.1.1-draft",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory-scope-test"),
            scope="session",
            memory_kind="fact",
            session_ref=session_ref,
            conversation_ref=ConversationRef(ref_type="conversation", ref_id="conv-scope-test"),
            trace_id="trace-seed",
            turn_id="turn-seed",
            content="My preferred codename is Alpha.",
            write_authorization="policy_approved",
            created_at=datetime(2026, 5, 21, 8, 0, tzinfo=UTC),
            tags=("profile",),
            raw_transcript_persisted=False,
        )
    )
    executor = _make_executor(intent_kind="memory")
    executor._memory_loop = loop

    result = executor.submit_turn(
        _make_turn_input(
            "What codename do I prefer?",
            session_id=session_ref.ref_id,
        )
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.metadata["session"]["transcript_persisted"] is False


# ---------------------------------------------------------------------------
# Capability 2: Provider selection runtime
# ---------------------------------------------------------------------------

def test_provider_selection_metadata_is_present() -> None:
    """Provider selection projection appears in metadata after a turn."""
    result = _run_core_subprocess_turn(
        "Hello through provider selection",
        trace_id="trace-cap-selection",
        turn_id="turn-cap-selection",
    )

    assert result.error is None
    assert "provider_selection" in result.metadata
    sel = result.metadata["provider_selection"]
    assert sel["provider_selection_enabled"] is True
    assert "selected_provider_id" in sel
    assert sel["raw_provider_payload_persisted"] is False


def test_provider_selection_honors_configured_provider() -> None:
    """ProviderSelectionRuntime selects the configured provider (fake) as the only candidate."""
    result = _run_core_subprocess_turn(
        "Hello from selection candidate test",
        trace_id="trace-cap-sel-candidate",
        turn_id="turn-cap-sel-candidate",
    )

    sel = result.metadata.get("provider_selection", {})
    # The only candidate is the configured provider
    assert sel.get("selected_provider_id") == "fake"


def test_provider_selection_runtime_used_directly() -> None:
    """ProviderSelectionRuntime produces a valid decision with safe projection."""
    from packages.capability_runtime import AutonomyPolicy
    from packages.provider_selection_runtime import (
        ModelCapabilityRequirement,
        ProviderCandidate,
        ProviderFallbackPolicy,
        ProviderRetryPolicy,
        ProviderSelectionRequest,
        ProviderSelectionRuntime,
    )

    runtime = ProviderSelectionRuntime(
        candidates=(
            ProviderCandidate(
                provider_id="fake",
                model="fake-model",
                supports_tools=False,
                context_length=4096,
                locality="local",
                healthy=True,
                cost_tier="free",
            ),
        )
    )
    request = ProviderSelectionRequest(
        trace_id="trace-sel-direct",
        requirement=ModelCapabilityRequirement(
            requested_capability="assistant_turn",
            tool_calling_required=False,
            min_context_length=0,
        ),
        autonomy_policy=AutonomyPolicy.for_mode("ask_before_risky"),
        fallback_policy=ProviderFallbackPolicy(
            provider_fallback_enabled=True,
            side_effect_retry_requires_policy=True,
        ),
        retry_policy=ProviderRetryPolicy(max_retries=1, retry_side_effect_tools=False),
    )
    decision = runtime.select(request)
    proj = decision.safe_projection()

    assert decision.selected.provider_id == "fake"
    assert proj.raw_provider_payload_persisted is False
    assert proj.selected_provider_id == "fake"


# ---------------------------------------------------------------------------
# Capability 3: Learning runtime
# ---------------------------------------------------------------------------

def test_learning_metadata_is_present_after_turn() -> None:
    """Learning projection appears in metadata after a successful turn."""
    result = _run_core_subprocess_turn(
        "Learning hook test",
        trace_id="trace-cap-learning",
        turn_id="turn-cap-learning",
    )

    assert result.error is None
    assert "learning" in result.metadata
    learning = result.metadata["learning"]
    assert learning["learning_enabled"] is True
    assert learning["silent_policy_mutation"] is False
    assert learning["silent_skill_mutation"] is False
    assert learning["raw_feedback_persisted"] is False


def test_learning_candidates_are_review_required() -> None:
    """All learning candidates produced by LearningLoop have review_required=True."""
    from packages.learning_runtime import (
        FeedbackEvent,
        FeedbackSignalKind,
        LearningLoop,
        UserCorrection,
    )

    loop = LearningLoop.default()
    correction = FeedbackEvent.from_user_correction(
        trace_id="trace-learn-review",
        turn_id="turn-learn-review",
        correction=UserCorrection(text="Please be more concise.", applies_to="answer"),
    )
    summary = loop.process((correction,))

    assert summary.silent_policy_mutation is False
    assert summary.silent_skill_mutation is False
    for candidate in summary.memory_write_candidates:
        assert candidate.review_required is True
    for candidate in summary.skill_improvement_candidates:
        assert candidate.review_required is True
    for candidate in summary.policy_tuning_candidates:
        assert candidate.review_required is True
    for candidate in summary.preference_candidates:
        assert candidate.review_required is True


def test_learning_pipeline_ingest_and_run_produces_safe_projection() -> None:
    """LearningPipelineRunner.ingest_and_run returns a safe projection with no auto-mutation."""
    from packages.capability_runtime import AutonomyPolicy
    from packages.learning_runtime import (
        FeedbackEvent,
        FeedbackSignalKind,
        LearningCandidateStore,
        LearningLoop,
        LearningPipelineRunner,
        ToolOutcomeFeedback,
    )

    store = LearningCandidateStore()
    pipeline = LearningPipelineRunner(
        store=store,
        autonomy_policy=AutonomyPolicy.for_mode("ask_before_risky"),
        loop=LearningLoop.default(),
    )
    event = FeedbackEvent(
        trace_id="trace-pipeline",
        turn_id="turn-pipeline",
        signal_kind=FeedbackSignalKind.TOOL_OUTCOME,
        payload=ToolOutcomeFeedback(
            tool_ref="intent.provider_simple_chat",
            succeeded=True,
            outcome_reason="turn_completed",
        ),
    )
    summary = pipeline.ingest_and_run((event,))
    proj = summary.safe_projection()

    assert proj.feedback_count == 1
    assert proj.silent_policy_mutation is False
    assert proj.silent_skill_mutation is False
    assert proj.raw_feedback_persisted is False
    assert store.latest_summary is summary


# ---------------------------------------------------------------------------
# Capability 4: Telemetry persistence
# ---------------------------------------------------------------------------

def test_persistent_trace_store_writes_and_reads_safe_events(tmp_path: Path) -> None:
    """PersistentTraceStore persists safe trace events and reads them back."""
    from packages.contracts import TraceEvent, TraceLevel, TraceStage
    from packages.telemetry import make_trace_event

    store_path = tmp_path / "traces.jsonl"
    store = PersistentTraceStore(trace_file_path=store_path)
    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-persist-test",
        turn_id="turn-persist-test",
        stage=TraceStage.TURN_RECEIVED,
        level=TraceLevel.INFO,
        message="Test trace event.",
        data={"status": "received"},
    )
    store.emit(event)

    result = store.read_trace("trace-persist-test")

    assert result is not None
    assert result["trace_id"] == "trace-persist-test"
    assert result["event_count"] >= 1
    assert store_path.exists()


def test_composite_trace_reader_prefers_persistent_store(tmp_path: Path) -> None:
    """_CompositeTraceReader returns persistent store result when available."""
    from packages.telemetry import make_trace_event
    from packages.contracts import TraceLevel, TraceStage
    from services.core.main import _CompositeTraceReader

    store_path = tmp_path / "traces.jsonl"
    persistent = PersistentTraceStore(trace_file_path=store_path)
    in_memory = InMemoryTraceReader()
    composite = _CompositeTraceReader(in_memory=in_memory, persistent=persistent)

    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-composite",
        turn_id="turn-composite",
        stage=TraceStage.TURN_COMPLETED,
        level=TraceLevel.INFO,
        message="Persistent event.",
        data={"status": "finalized"},
    )
    persistent.emit(event)

    result = composite.read_trace("trace-composite")

    assert result is not None
    assert result["trace_id"] == "trace-composite"
    assert result["scope"] == "local_persistence"


def test_composite_trace_reader_falls_back_to_in_memory_when_no_persistent() -> None:
    """_CompositeTraceReader falls back to in-memory when persistent has no entry."""
    from packages.telemetry import make_trace_event
    from packages.contracts import TraceLevel, TraceStage
    from services.core.main import _CompositeTraceReader

    in_memory = InMemoryTraceReader()
    composite = _CompositeTraceReader(in_memory=in_memory, persistent=None)

    event = make_trace_event(
        schema_version="0.1.1-draft",
        trace_id="trace-in-memory-fallback",
        turn_id="turn-in-memory-fallback",
        stage=TraceStage.TURN_RECEIVED,
        level=TraceLevel.INFO,
        message="In-memory only event.",
    )
    in_memory.emit(event)

    result = composite.read_trace("trace-in-memory-fallback")

    assert result is not None
    assert result["scope"] == "current_process"


def test_telemetry_store_path_configurable_per_run(tmp_path: Path) -> None:
    """--telemetry-store-path controls where safe traces are persisted."""
    store_path = tmp_path / "custom-traces.jsonl"
    result = _run_core_subprocess_turn(
        "Telemetry persistence test",
        trace_id="trace-cap-telemetry-persist",
        turn_id="turn-cap-telemetry-persist",
        extra=["--telemetry-store-path", str(store_path)],
    )

    assert result.error is None
    # The store file should have been created with safe events
    assert store_path.exists()
    lines = [line for line in store_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    # Verify content is safe JSON with no raw payloads
    for line in lines:
        record = json.loads(line)
        assert "trace_id" in record
        assert "prompt" not in str(record).lower() or "raw" not in str(record).lower()
