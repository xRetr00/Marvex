from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from packages.contracts import (
    AssistantTurnInput,
    AssistantTurnResult,
    ConversationRef,
    SessionRef,
    StageStatus,
)


class AssistantStageName(str, Enum):
    INPUT_NORMALIZATION = "input_normalization"
    SESSION_CONVERSATION_LINKAGE = "session_conversation_linkage"
    RUNTIME_STATE_SNAPSHOT = "runtime_state_snapshot"
    MEMORY_READ_POLICY = "memory_read_policy"
    PROVIDER_STAGE_PREPARATION = "provider_stage_preparation"
    PROVIDER_RESULT_CONSUMPTION = "provider_result_consumption"
    FINAL_RESPONSE_ASSEMBLY = "final_response_assembly"
    MEMORY_WRITE_CANDIDATE = "memory_write_candidate"
    MEMORY_POLICY_HOOKS = "memory_policy_hooks"
    TELEMETRY_TRACE_LINKAGE = "telemetry_trace_linkage"


STAGE_ORDER: tuple[AssistantStageName, ...] = (
    AssistantStageName.INPUT_NORMALIZATION,
    AssistantStageName.SESSION_CONVERSATION_LINKAGE,
    AssistantStageName.RUNTIME_STATE_SNAPSHOT,
    AssistantStageName.MEMORY_READ_POLICY,
    AssistantStageName.PROVIDER_STAGE_PREPARATION,
    AssistantStageName.PROVIDER_RESULT_CONSUMPTION,
    AssistantStageName.FINAL_RESPONSE_ASSEMBLY,
    AssistantStageName.MEMORY_WRITE_CANDIDATE,
    AssistantStageName.MEMORY_POLICY_HOOKS,
    AssistantStageName.TELEMETRY_TRACE_LINKAGE,
)
_STAGE_INDEX = {stage: index for index, stage in enumerate(STAGE_ORDER)}


@dataclass(frozen=True)
class AssistantStageResult:
    schema_version: str
    trace_id: str
    turn_id: str
    stage_name: AssistantStageName
    status: StageStatus
    ref_present: bool = False
    error_ref_present: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "stage_name": self.stage_name.value,
            "status": self.status.value,
            "ref_present": self.ref_present,
            "error_ref_present": self.error_ref_present,
        }


@dataclass(frozen=True)
class AssistantTurnLifecycleSummary:
    schema_version: str
    trace_id: str
    turn_id: str
    stage_results: tuple[AssistantStageResult, ...]
    session_ref: SessionRef | None
    conversation_ref: ConversationRef | None
    previous_response_id_present: bool
    provider_response_id_present: bool
    final_response_present: bool
    error_code: str | None
    provider_turn_ref_count: int
    memory_result_ref_count: int
    output_event_count: int
    memory_read_ready: bool
    memory_read_ref_count: int
    memory_write_candidate_ready: bool
    memory_write_candidate_ref_count: int
    memory_policy_decision_ref_count: int
    memory_forget_ready: bool
    telemetry_event_count: int
    persistent_trace_linked: bool
    capability_readiness_count: int = 0
    selected_eligible_capability_count: int = 0
    denied_capability_count: int = 0
    executed_fake_capability_count: int = 0
    capability_safe_result_status: str | None = None
    agent_loop_step_count: int = 0
    tool_result_delivery_ready: bool = False
    transcript_persisted: bool = False
    raw_payload_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "stage_results": [stage.safe_projection() for stage in self.stage_results],
            "session_ref": _dump_ref(self.session_ref),
            "conversation_ref": _dump_ref(self.conversation_ref),
            "previous_response_id_present": self.previous_response_id_present,
            "provider_response_id_present": self.provider_response_id_present,
            "final_response_present": self.final_response_present,
            "error_code": self.error_code,
            "provider_turn_ref_count": self.provider_turn_ref_count,
            "memory_result_ref_count": self.memory_result_ref_count,
            "output_event_count": self.output_event_count,
            "memory_read_ready": self.memory_read_ready,
            "memory_read_ref_count": self.memory_read_ref_count,
            "memory_write_candidate_ready": self.memory_write_candidate_ready,
            "memory_write_candidate_ref_count": self.memory_write_candidate_ref_count,
            "memory_policy_decision_ref_count": self.memory_policy_decision_ref_count,
            "memory_forget_ready": self.memory_forget_ready,
            "telemetry_event_count": self.telemetry_event_count,
            "persistent_trace_linked": self.persistent_trace_linked,
            "capability_readiness_count": self.capability_readiness_count,
            "selected_eligible_capability_count": self.selected_eligible_capability_count,
            "denied_capability_count": self.denied_capability_count,
            "executed_fake_capability_count": self.executed_fake_capability_count,
            "capability_safe_result_status": self.capability_safe_result_status,
            "agent_loop_step_count": self.agent_loop_step_count,
            "tool_result_delivery_ready": self.tool_result_delivery_ready,
            "transcript_persisted": False,
            "raw_payload_persisted": False,
        }


def build_turn_lifecycle_summary(
    turn_input: AssistantTurnInput,
    *,
    result: AssistantTurnResult | None = None,
    conversation_ref: ConversationRef | None = None,
    previous_response_id: str | None = None,
    provider_response_id: str | None = None,
    memory_read_ready: bool = False,
    memory_read_ref_count: int = 0,
    memory_write_candidate_ready: bool = False,
    memory_write_candidate_ref_count: int = 0,
    memory_policy_decision_ref_count: int = 0,
    memory_forget_ready: bool = False,
    telemetry_event_count: int = 0,
    persistent_trace_linked: bool = False,
    capability_readiness_count: int = 0,
    selected_eligible_capability_count: int = 0,
    denied_capability_count: int = 0,
    executed_fake_capability_count: int = 0,
    capability_safe_result_status: str | None = None,
) -> AssistantTurnLifecycleSummary:
    _validate_counts(
        memory_read_ref_count=memory_read_ref_count,
        memory_write_candidate_ref_count=memory_write_candidate_ref_count,
        memory_policy_decision_ref_count=memory_policy_decision_ref_count,
        telemetry_event_count=telemetry_event_count,
        capability_readiness_count=capability_readiness_count,
        selected_eligible_capability_count=selected_eligible_capability_count,
        denied_capability_count=denied_capability_count,
        executed_fake_capability_count=executed_fake_capability_count,
    )
    if result is not None:
        _validate_result_identity(turn_input, result)

    stage_results = _build_stage_results(
        turn_input,
        result=result,
        conversation_ref=conversation_ref,
        provider_response_id_present=bool(provider_response_id),
        memory_read_ready=memory_read_ready,
        memory_write_candidate_ready=memory_write_candidate_ready,
        memory_write_candidate_ref_count=memory_write_candidate_ref_count,
        memory_policy_decision_ref_count=memory_policy_decision_ref_count,
        memory_forget_ready=memory_forget_ready,
        telemetry_event_count=telemetry_event_count,
        persistent_trace_linked=persistent_trace_linked,
    )

    return AssistantTurnLifecycleSummary(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        stage_results=stage_results,
        session_ref=turn_input.session_ref,
        conversation_ref=conversation_ref,
        previous_response_id_present=bool(previous_response_id),
        provider_response_id_present=bool(provider_response_id),
        final_response_present=(
            result is not None and result.assistant_final_response is not None
        ),
        error_code=(result.error.code.value if result is not None and result.error else None),
        provider_turn_ref_count=(len(result.provider_turn_refs) if result is not None else 0),
        memory_result_ref_count=(len(result.memory_result_refs) if result is not None else 0),
        output_event_count=(len(result.output_events) if result is not None else 0),
        memory_read_ready=memory_read_ready,
        memory_read_ref_count=memory_read_ref_count,
        memory_write_candidate_ready=memory_write_candidate_ready,
        memory_write_candidate_ref_count=memory_write_candidate_ref_count,
        memory_policy_decision_ref_count=memory_policy_decision_ref_count,
        memory_forget_ready=memory_forget_ready,
        telemetry_event_count=telemetry_event_count,
        persistent_trace_linked=persistent_trace_linked,
        capability_readiness_count=capability_readiness_count,
        selected_eligible_capability_count=selected_eligible_capability_count,
        denied_capability_count=denied_capability_count,
        executed_fake_capability_count=executed_fake_capability_count,
        capability_safe_result_status=capability_safe_result_status,
        transcript_persisted=False,
        raw_payload_persisted=False,
    )


def validate_lifecycle_transition(
    from_stage: AssistantStageName,
    to_stage: AssistantStageName,
) -> bool:
    if _STAGE_INDEX[to_stage] < _STAGE_INDEX[from_stage]:
        raise ValueError("assistant lifecycle stage transitions must not move backwards")
    return True


def _build_stage_results(
    turn_input: AssistantTurnInput,
    *,
    result: AssistantTurnResult | None,
    conversation_ref: ConversationRef | None,
    provider_response_id_present: bool,
    memory_read_ready: bool,
    memory_write_candidate_ready: bool,
    memory_write_candidate_ref_count: int,
    memory_policy_decision_ref_count: int,
    memory_forget_ready: bool,
    telemetry_event_count: int,
    persistent_trace_linked: bool,
) -> tuple[AssistantStageResult, ...]:
    provider_status = _provider_status(result, provider_response_id_present)
    final_status = _final_response_status(result)
    policy_hooks_ready = (
        memory_read_ready
        or memory_write_candidate_ready
        or memory_forget_ready
        or memory_policy_decision_ref_count > 0
    )

    specs = (
        (AssistantStageName.INPUT_NORMALIZATION, StageStatus.COMPLETED, True, False),
        (
            AssistantStageName.SESSION_CONVERSATION_LINKAGE,
            _completed_if(turn_input.session_ref is not None or conversation_ref is not None),
            turn_input.session_ref is not None or conversation_ref is not None,
            False,
        ),
        (AssistantStageName.RUNTIME_STATE_SNAPSHOT, StageStatus.COMPLETED, True, False),
        (AssistantStageName.MEMORY_READ_POLICY, _completed_if(memory_read_ready), memory_read_ready, False),
        (AssistantStageName.PROVIDER_STAGE_PREPARATION, StageStatus.COMPLETED, True, False),
        (
            AssistantStageName.PROVIDER_RESULT_CONSUMPTION,
            provider_status,
            provider_response_id_present,
            provider_status == StageStatus.FAILED,
        ),
        (
            AssistantStageName.FINAL_RESPONSE_ASSEMBLY,
            final_status,
            result is not None and result.assistant_final_response is not None,
            final_status == StageStatus.FAILED,
        ),
        (
            AssistantStageName.MEMORY_WRITE_CANDIDATE,
            _completed_if(memory_write_candidate_ready),
            memory_write_candidate_ref_count > 0,
            False,
        ),
        (
            AssistantStageName.MEMORY_POLICY_HOOKS,
            _completed_if(policy_hooks_ready),
            policy_hooks_ready,
            False,
        ),
        (
            AssistantStageName.TELEMETRY_TRACE_LINKAGE,
            _completed_if(telemetry_event_count > 0 or persistent_trace_linked),
            telemetry_event_count > 0 or persistent_trace_linked,
            False,
        ),
    )

    return tuple(
        AssistantStageResult(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            stage_name=stage_name,
            status=status,
            ref_present=ref_present,
            error_ref_present=error_ref_present,
        )
        for stage_name, status, ref_present, error_ref_present in specs
    )


def _provider_status(
    result: AssistantTurnResult | None,
    provider_response_id_present: bool,
) -> StageStatus:
    if result is None and not provider_response_id_present:
        return StageStatus.SKIPPED
    if result is not None and result.error is not None and not provider_response_id_present:
        return StageStatus.FAILED
    return StageStatus.COMPLETED


def _final_response_status(result: AssistantTurnResult | None) -> StageStatus:
    if result is None:
        return StageStatus.SKIPPED
    if result.error is not None:
        return StageStatus.FAILED
    return StageStatus.COMPLETED


def _completed_if(value: bool) -> StageStatus:
    return StageStatus.COMPLETED if value else StageStatus.SKIPPED


def _validate_result_identity(
    turn_input: AssistantTurnInput,
    result: AssistantTurnResult,
) -> None:
    if result.trace_id != turn_input.trace_id:
        raise ValueError("assistant lifecycle result trace_id must match turn input")
    if result.turn_id != turn_input.turn_id:
        raise ValueError("assistant lifecycle result turn_id must match turn input")
    if result.schema_version != turn_input.schema_version:
        raise ValueError("assistant lifecycle result schema_version must match turn input")


def _validate_counts(**counts: int) -> None:
    for name, value in counts.items():
        if value < 0:
            raise ValueError(f"assistant lifecycle {name} must be non-negative")


def _dump_ref(ref: SessionRef | ConversationRef | None) -> dict[str, str] | None:
    if ref is None:
        return None
    return ref.model_dump()


