from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import packages.contracts as contracts


def _contract(name: str):
    assert hasattr(contracts, name), f"{name} must be exported from packages.contracts"
    return getattr(contracts, name)


def _privacy() -> dict[str, object]:
    return {"sensitivity": "normal", "redaction_needed": False}


def _policy_context() -> dict[str, object]:
    return {"requested_capabilities": [], "sensitivity": "normal"}


def _assistant_final_response():
    return _contract("AssistantFinalResponse")(
        schema_version="0.1.1-draft",
        response_type=_contract("AssistantResponseType").TEXT,
        text="Hello.",
        payload_ref=None,
        output_channel_intent=_contract("OutputChannelIntent").DEFAULT,
        safe_for_display=True,
        safe_for_speech=True,
        memory_write_candidate_hint=False,
        finish_reason=_contract("AssistantFinishReason").STOP,
        metadata={},
    )


def _error():
    return contracts.ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-003",
        error_id="error-001",
        code=contracts.ErrorCode.VALIDATION_ERROR,
        message="Input event validation failed.",
        recoverable=False,
        source="assistant_turn",
        details={},
    )


def test_input_event_accepts_text_payload():
    event = _contract("InputEvent")(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        source=_contract("AssistantInputSource").CLI,
        input_modality=_contract("InputModality").TEXT,
        payload={"kind": "text", "text": "Hello"},
        payload_ref=None,
        session_ref=None,
        privacy=_privacy(),
        timestamp=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        metadata={},
    )

    assert event.payload is not None
    assert event.payload.model_dump() == {"kind": "text", "text": "Hello"}
    assert event.payload_ref is None
    assert event.privacy.sensitivity == "normal"


def test_input_event_accepts_payload_ref():
    event = _contract("InputEvent")(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        source="cli",
        input_modality="text",
        payload=None,
        payload_ref={
            "ref_type": "payload",
            "ref_id": "payload-001",
            "kind": "text",
            "uri": None,
        },
        session_ref=None,
        privacy=_privacy(),
        timestamp=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        metadata={},
    )

    assert event.payload is None
    assert event.payload_ref.ref_id == "payload-001"


def test_input_event_rejects_both_payload_and_payload_ref():
    with pytest.raises(ValidationError):
        _contract("InputEvent")(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            event_id="event-001",
            source="cli",
            input_modality="text",
            payload={"kind": "text", "text": "Hello"},
            payload_ref={
                "ref_type": "payload",
                "ref_id": "payload-001",
                "kind": "text",
                "uri": None,
            },
            session_ref=None,
            privacy=_privacy(),
            timestamp=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            metadata={},
        )


def test_input_event_rejects_neither_payload_nor_payload_ref():
    with pytest.raises(ValidationError):
        _contract("InputEvent")(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            event_id="event-001",
            source="cli",
            input_modality="text",
            payload=None,
            payload_ref=None,
            session_ref=None,
            privacy=_privacy(),
            timestamp=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            metadata={},
        )


def test_input_event_rejects_invalid_enum_values():
    with pytest.raises(ValidationError):
        _contract("InputEvent")(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            event_id="event-001",
            source="provider",
            input_modality="text",
            payload={"kind": "text", "text": "Hello"},
            payload_ref=None,
            session_ref=None,
            privacy=_privacy(),
            timestamp=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            metadata={},
        )


def test_assistant_turn_input_accepts_valid_shape():
    turn_input = _contract("AssistantTurnInput")(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_event_id="event-001",
        session_ref={"ref_type": "session", "ref_id": "session-001"},
        identity_ref={"ref_type": "identity", "ref_id": "local-profile-001"},
        user_visible_input="Hello",
        assistant_mode=_contract("AssistantMode").DEFAULT,
        policy_context=_policy_context(),
        metadata={},
    )

    assert turn_input.session_ref.ref_id == "session-001"
    assert turn_input.identity_ref.ref_id == "local-profile-001"
    assert turn_input.policy_context.requested_capabilities == []


def test_assistant_turn_input_rejects_policy_context_decision_shape():
    with pytest.raises(ValidationError):
        _contract("AssistantTurnInput")(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            input_event_id="event-001",
            session_ref=None,
            identity_ref=None,
            user_visible_input="Hello",
            assistant_mode="default",
            policy_context={
                "requested_capabilities": [],
                "sensitivity": "normal",
                "allow": True,
            },
            metadata={},
        )


def test_assistant_turn_result_accepts_success_without_provider_call():
    result = _contract("AssistantTurnResult")(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        assistant_final_response=_assistant_final_response(),
        output_events=[],
        stage_summaries=[
            {
                "stage_name": "final_response_assembly",
                "status": _contract("StageStatus").COMPLETED,
                "started_at": None,
                "completed_at": None,
                "ref": None,
                "error_ref": None,
            }
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )

    assert result.provider_turn_refs == []
    assert result.stage_summaries[0].status == _contract("StageStatus").COMPLETED


def test_assistant_turn_result_accepts_success_with_provider_ref():
    result = _contract("AssistantTurnResult")(
        schema_version="0.1.1-draft",
        trace_id="trace-002",
        turn_id="turn-002",
        assistant_final_response=_assistant_final_response(),
        output_events=[],
        stage_summaries=[
            {
                "stage_name": "provider_reasoning",
                "status": "completed",
                "started_at": None,
                "completed_at": None,
                "ref": "provider-turn-001",
                "error_ref": None,
            }
        ],
        provider_turn_refs=[
            {
                "ref_type": "provider_turn",
                "ref_id": "provider-turn-001",
                "stage_name": "provider_reasoning",
                "provider_name": "fake",
                "status": "completed",
                "trace_id": "trace-002",
            }
        ],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )

    assert result.provider_turn_refs[0].ref_id == "provider-turn-001"


def test_assistant_turn_result_accepts_hard_failure_with_error():
    result = _contract("AssistantTurnResult")(
        schema_version="0.1.1-draft",
        trace_id="trace-003",
        turn_id="turn-003",
        assistant_final_response=None,
        output_events=[],
        stage_summaries=[
            {
                "stage_name": "input_normalization",
                "status": "failed",
                "started_at": None,
                "completed_at": None,
                "ref": None,
                "error_ref": "error-001",
            }
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=_error(),
        metadata={},
    )

    assert result.assistant_final_response is None
    assert result.error is not None


def test_assistant_turn_result_rejects_missing_final_response_and_error():
    with pytest.raises(ValidationError):
        _contract("AssistantTurnResult")(
            schema_version="0.1.1-draft",
            trace_id="trace-003",
            turn_id="turn-003",
            assistant_final_response=None,
            output_events=[],
            stage_summaries=[],
            provider_turn_refs=[],
            tool_result_refs=[],
            memory_result_refs=[],
            session_result_ref=None,
            error=None,
            metadata={},
        )


def test_assistant_final_response_accepts_text():
    response = _assistant_final_response()

    assert response.response_type == _contract("AssistantResponseType").TEXT
    assert response.text == "Hello."
    assert response.payload_ref is None


def test_assistant_final_response_accepts_error():
    response = _contract("AssistantFinalResponse")(
        schema_version="0.1.1-draft",
        response_type=_contract("AssistantResponseType").ERROR,
        text="I could not complete that request.",
        payload_ref=None,
        output_channel_intent=_contract("OutputChannelIntent").DISPLAY,
        safe_for_display=True,
        safe_for_speech=False,
        memory_write_candidate_hint=False,
        finish_reason=_contract("AssistantFinishReason").ERROR,
        metadata={},
    )

    assert response.response_type == _contract("AssistantResponseType").ERROR


def test_assistant_final_response_rejects_text_response_without_text():
    with pytest.raises(ValidationError):
        _contract("AssistantFinalResponse")(
            schema_version="0.1.1-draft",
            response_type="text",
            text=None,
            payload_ref=None,
            output_channel_intent="default",
            safe_for_display=True,
            safe_for_speech=True,
            memory_write_candidate_hint=False,
            finish_reason="stop",
            metadata={},
        )


def test_assistant_final_response_rejects_payload_ref_response_without_payload_ref():
    with pytest.raises(ValidationError):
        _contract("AssistantFinalResponse")(
            schema_version="0.1.1-draft",
            response_type="payload_ref",
            text=None,
            payload_ref=None,
            output_channel_intent="display",
            safe_for_display=True,
            safe_for_speech=False,
            memory_write_candidate_hint=False,
            finish_reason="stop",
            metadata={},
        )


def test_provider_foundation_contracts_still_construct_as_before():
    final_response = contracts.FinalResponse(
        text="Hello.",
        response_type=contracts.ResponseType.TEXT,
        finish_reason=contracts.FinishReason.STOP,
        safe_for_tts=True,
        metadata={},
    )
    turn_input = contracts.TurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-provider",
        turn_id="turn-provider",
        input_text="Hello",
        previous_response_id=None,
        source=contracts.Source.CLI,
        metadata={},
    )
    provider_request = contracts.ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-provider",
        turn_id="turn-provider",
        model="local-model",
        input_text="Hello",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )
    provider_response = contracts.ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-provider",
        turn_id="turn-provider",
        provider_name="fake",
        response_id=None,
        output_text="Hello.",
        finish_reason=contracts.FinishReason.STOP,
        usage={},
        raw_metadata={},
        error=None,
    )
    turn_output = contracts.TurnOutput(
        schema_version="0.1.1-draft",
        trace_id="trace-provider",
        turn_id="turn-provider",
        final_response=final_response,
        provider_response_id=None,
        events=[],
        error=None,
    )

    assert turn_input.input_text == "Hello"
    assert provider_request.provider_options == {}
    assert provider_response.raw_metadata == {}
    assert turn_output.final_response is final_response
