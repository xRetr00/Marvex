from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.contracts import AssistantTurnInput, AssistantTurnResult


REDACTED = "[REDACTED]"
_UNSAFE_KEY_PARTS = (
    "authorization",
    "bearer",
    "password",
    "prompt",
    "raw",
    "secret",
    "token",
    "transcript",
)
_UNSAFE_STRING_TERMS = (
    "authorization",
    "bearer",
    "provider output",
    "raw provider",
    "secret",
    "token",
    "transcript",
)


@dataclass(frozen=True)
class TurnStateSnapshot:
    schema_version: str
    trace_id: str
    turn_id: str
    input_event_id: str
    previous_response_id_present: bool
    session_ref_present: bool
    user_visible_input_present: bool
    metadata_keys: tuple[str, ...]
    transcript_persisted: bool = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "input_event_id": self.input_event_id,
            "previous_response_id_present": self.previous_response_id_present,
            "session_ref_present": self.session_ref_present,
            "user_visible_input_present": self.user_visible_input_present,
            "metadata_keys": list(self.metadata_keys),
            "transcript_persisted": self.transcript_persisted,
        }


@dataclass(frozen=True)
class AssistantTurnExecutionSummary:
    schema_version: str
    trace_id: str
    turn_id: str
    completed: bool
    error_code: str | None
    final_response_present: bool
    provider_ref_count: int
    tool_ref_count: int
    memory_ref_count: int
    output_event_count: int
    stage_statuses: dict[str, str]

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "completed": self.completed,
            "error_code": self.error_code,
            "final_response_present": self.final_response_present,
            "provider_ref_count": self.provider_ref_count,
            "tool_ref_count": self.tool_ref_count,
            "memory_ref_count": self.memory_ref_count,
            "output_event_count": self.output_event_count,
            "stage_statuses": dict(self.stage_statuses),
        }


@dataclass(frozen=True)
class StateTransitionRecord:
    schema_version: str
    trace_id: str
    turn_id: str
    sequence: int
    from_state: str
    to_state: str
    reason: str

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "from_state": _safe_text(self.from_state),
            "to_state": _safe_text(self.to_state),
            "reason": _safe_text(self.reason),
        }


def build_turn_state_snapshot(
    turn_input: AssistantTurnInput,
    *,
    previous_response_id: str | None = None,
) -> TurnStateSnapshot:
    return TurnStateSnapshot(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        input_event_id=turn_input.input_event_id,
        previous_response_id_present=bool(previous_response_id),
        session_ref_present=turn_input.session_ref is not None,
        user_visible_input_present=bool(turn_input.user_visible_input),
        metadata_keys=safe_state_metadata_keys(turn_input.metadata),
    )


def build_execution_summary(
    result: AssistantTurnResult,
) -> AssistantTurnExecutionSummary:
    return AssistantTurnExecutionSummary(
        schema_version=result.schema_version,
        trace_id=result.trace_id,
        turn_id=result.turn_id,
        completed=result.error is None,
        error_code=result.error.code.value if result.error is not None else None,
        final_response_present=result.assistant_final_response is not None,
        provider_ref_count=len(result.provider_turn_refs),
        tool_ref_count=len(result.tool_result_refs),
        memory_ref_count=len(result.memory_result_refs),
        output_event_count=len(result.output_events),
        stage_statuses={
            _safe_text(stage.stage_name): stage.status.value
            for stage in result.stage_summaries
        },
    )


def _safe_text(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in _UNSAFE_STRING_TERMS):
        return REDACTED
    return value


def safe_state_metadata_keys(metadata: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            REDACTED if _unsafe_key(str(key)) else str(key)
            for key in metadata
        )
    )


def _unsafe_key(value: str) -> bool:
    normalized = "".join(character for character in value.lower() if character.isalnum())
    return any(part in normalized for part in _UNSAFE_KEY_PARTS)
