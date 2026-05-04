import pytest
from pydantic import ValidationError

from packages.contracts import AssistantFinishReason, ErrorCode, StageStatus
from packages.assistant_runtime.result_assembly import (
    build_hard_failure_turn_result,
    build_text_final_response,
    build_text_success_turn_result,
)


def test_invalid_empty_or_whitespace_final_response_text_is_rejected():
    for text in ["", "   "]:
        with pytest.raises(ValidationError):
            build_text_final_response(
                schema_version="0.1.1-draft",
                text=text,
            )


def test_success_result_assembly_returns_turn_result_with_final_response():
    result = build_text_success_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        text="Done.",
    )

    assert result.trace_id == "trace-001"
    assert result.turn_id == "turn-001"
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Done."
    assert result.assistant_final_response.memory_write_candidate_hint is False
    assert result.provider_turn_refs == []
    assert result.tool_result_refs == []
    assert result.memory_result_refs == []
    assert result.error is None


def test_hard_failure_result_assembly_returns_error_without_final_response():
    result = build_hard_failure_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        error_id="error-001",
        code=ErrorCode.VALIDATION_ERROR,
        message="Input validation failed.",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.error_id == "error-001"
    assert result.error.trace_id == "trace-001"
    assert result.stage_summaries[0].status == StageStatus.FAILED
    assert result.stage_summaries[0].error_ref == "error-001"


def test_result_assembly_does_not_create_provider_response_id():
    result = build_text_success_turn_result(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        text="Done.",
    )

    dumped = result.model_dump()

    assert "provider_response_id" not in dumped
    assert all("provider_response_id" not in ref for ref in dumped["provider_turn_refs"])


def test_text_final_response_uses_safe_defaults():
    response = build_text_final_response(
        schema_version="0.1.1-draft",
        text="Ready.",
    )

    assert response.finish_reason == AssistantFinishReason.STOP
    assert response.safe_for_display is True
    assert response.safe_for_speech is True
    assert response.memory_write_candidate_hint is False
    assert response.metadata == {}
