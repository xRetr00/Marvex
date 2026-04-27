from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinalResponse,
    FinishReason,
    HealthCheck,
    HealthStatus,
    ProviderRequest,
    ResponseType,
    Source,
    TraceEvent,
    TraceLevel,
    TraceStage,
    TurnInput,
    TurnOutput,
    VersionInfo,
)


def test_turn_input_accepts_documented_shape():
    turn = TurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_text="Hello",
        previous_response_id="resp-previous",
        source=Source.CLI,
        metadata={},
    )

    assert turn.previous_response_id == "resp-previous"
    assert turn.source == Source.CLI
    assert turn.metadata == {}


def test_required_fields_are_enforced():
    with pytest.raises(ValidationError):
        TurnInput(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            input_text="Hello",
            previous_response_id=None,
            source=Source.CLI,
            metadata={},
        )


def test_required_ids_reject_empty_strings():
    with pytest.raises(ValidationError):
        TurnInput(
            schema_version="0.1.1-draft",
            trace_id="",
            turn_id="turn-001",
            input_text="Hello",
            previous_response_id=None,
            source=Source.CLI,
            metadata={},
        )


def test_unknown_top_level_fields_are_rejected():
    with pytest.raises(ValidationError):
        TurnInput(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            input_text="Hello",
            previous_response_id=None,
            source=Source.CLI,
            metadata={},
            unexpected=True,
        )


def test_turn_input_previous_response_id_is_required_and_nullable():
    with_previous = TurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_text="Hello",
        previous_response_id="resp-001",
        source=Source.CLI,
        metadata={},
    )
    with_null = TurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_text="Hello",
        previous_response_id=None,
        source=Source.CLI,
        metadata={},
    )

    assert with_previous.previous_response_id == "resp-001"
    assert with_null.previous_response_id is None

    with pytest.raises(ValidationError):
        TurnInput(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            input_text="Hello",
            source=Source.CLI,
            metadata={},
        )


def test_invalid_enum_values_are_rejected():
    with pytest.raises(ValidationError):
        FinalResponse(
            text="Hello.",
            response_type="audio",
            finish_reason=FinishReason.STOP,
            safe_for_tts=True,
            metadata={},
        )


def test_nullable_required_fields_must_be_present_and_may_be_null():
    request = ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        model="local-model",
        input_text="Hello",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )

    assert request.instructions is None
    assert request.previous_response_id is None

    with pytest.raises(ValidationError):
        ProviderRequest(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            model="local-model",
            input_text="Hello",
            instructions=None,
            provider_options={},
        )


def test_error_envelope_accepts_known_codes_and_rejects_unknown_codes():
    envelope = ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        error_id="error-001",
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid input.",
        recoverable=True,
        source="contracts",
        details={},
    )

    assert envelope.code == ErrorCode.VALIDATION_ERROR

    with pytest.raises(ValidationError):
        ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-001",
            error_id="error-001",
            code="UNKNOWN_CODE",
            message="Invalid input.",
            recoverable=True,
            source="contracts",
            details={},
        )


def test_turn_output_accepts_nested_response_events_and_nullable_error():
    response = FinalResponse(
        text="Hello.",
        response_type=ResponseType.TEXT,
        finish_reason=FinishReason.STOP,
        safe_for_tts=True,
        metadata={},
    )
    event = TraceEvent(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        timestamp=datetime(2026, 4, 24, 12, 0, tzinfo=UTC),
        stage=TraceStage.TURN_COMPLETED,
        level=TraceLevel.INFO,
        message="Turn completed.",
        data={},
    )

    output = TurnOutput(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        final_response=response,
        provider_response_id=None,
        events=[event],
        error=None,
    )

    assert output.final_response.text == "Hello."
    assert output.provider_response_id is None
    assert output.error is None


def test_health_check_rejects_negative_uptime():
    with pytest.raises(ValidationError):
        HealthCheck(
            schema_version="0.1.1-draft",
            service="core",
            status=HealthStatus.OK,
            version="0.1.0",
            uptime_seconds=-1,
            dependencies={},
        )


def test_health_check_accepts_valid_shape():
    health = HealthCheck(
        schema_version="0.1.1-draft",
        service="core",
        status=HealthStatus.OK,
        version="0.1.0",
        uptime_seconds=0,
        dependencies={},
    )

    assert health.schema_version == "0.1.1-draft"
    assert health.service == "core"
    assert health.status == HealthStatus.OK
    assert health.version == "0.1.0"
    assert health.uptime_seconds == 0
    assert health.dependencies == {}


def test_health_check_accepts_all_allowed_status_values():
    for status in HealthStatus:
        health = HealthCheck(
            schema_version="0.1.1-draft",
            service="core",
            status=status.value,
            version="0.1.0",
            uptime_seconds=1.0,
            dependencies={},
        )

        assert health.status == status


def test_health_check_rejects_unknown_status():
    with pytest.raises(ValidationError):
        HealthCheck(
            schema_version="0.1.1-draft",
            service="core",
            status="unknown",
            version="0.1.0",
            uptime_seconds=1.0,
            dependencies={},
        )


@pytest.mark.parametrize(
    "missing_field",
    [
        "schema_version",
        "service",
        "status",
        "version",
        "uptime_seconds",
        "dependencies",
    ],
)
def test_health_check_rejects_missing_required_fields(missing_field):
    payload = {
        "schema_version": "0.1.1-draft",
        "service": "core",
        "status": HealthStatus.OK,
        "version": "0.1.0",
        "uptime_seconds": 1.0,
        "dependencies": {},
    }
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        HealthCheck(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service", ""),
        ("version", ""),
    ],
)
def test_health_check_rejects_empty_service_and_version(field, value):
    payload = {
        "schema_version": "0.1.1-draft",
        "service": "core",
        "status": HealthStatus.OK,
        "version": "0.1.0",
        "uptime_seconds": 1.0,
        "dependencies": {},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        HealthCheck(**payload)


def test_health_check_rejects_non_object_dependencies():
    with pytest.raises(ValidationError):
        HealthCheck(
            schema_version="0.1.1-draft",
            service="core",
            status=HealthStatus.OK,
            version="0.1.0",
            uptime_seconds=1.0,
            dependencies=[],
        )


def test_health_check_rejects_extra_fields():
    with pytest.raises(ValidationError):
        HealthCheck(
            schema_version="0.1.1-draft",
            service="core",
            status=HealthStatus.OK,
            version="0.1.0",
            uptime_seconds=1.0,
            dependencies={},
            endpoint="/health",
        )


def test_version_info_accepts_valid_shape():
    version = VersionInfo(
        schema_version="0.1.1-draft",
        service="core",
        service_version="0.1.0",
        contract_versions={"HealthCheck": "0.1.1-draft"},
        build={},
    )

    assert version.schema_version == "0.1.1-draft"
    assert version.service == "core"
    assert version.service_version == "0.1.0"
    assert version.contract_versions == {"HealthCheck": "0.1.1-draft"}
    assert version.build == {}


@pytest.mark.parametrize(
    "missing_field",
    [
        "schema_version",
        "service",
        "service_version",
        "contract_versions",
        "build",
    ],
)
def test_version_info_rejects_missing_required_fields(missing_field):
    payload = {
        "schema_version": "0.1.1-draft",
        "service": "core",
        "service_version": "0.1.0",
        "contract_versions": {"HealthCheck": "0.1.1-draft"},
        "build": {},
    }
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        VersionInfo(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service", ""),
        ("service_version", ""),
    ],
)
def test_version_info_rejects_empty_service_and_service_version(field, value):
    payload = {
        "schema_version": "0.1.1-draft",
        "service": "core",
        "service_version": "0.1.0",
        "contract_versions": {"HealthCheck": "0.1.1-draft"},
        "build": {},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        VersionInfo(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contract_versions", []),
        ("build", []),
    ],
)
def test_version_info_rejects_non_object_contract_versions_and_build(field, value):
    payload = {
        "schema_version": "0.1.1-draft",
        "service": "core",
        "service_version": "0.1.0",
        "contract_versions": {"HealthCheck": "0.1.1-draft"},
        "build": {},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        VersionInfo(**payload)


def test_version_info_rejects_extra_fields():
    with pytest.raises(ValidationError):
        VersionInfo(
            schema_version="0.1.1-draft",
            service="core",
            service_version="0.1.0",
            contract_versions={"HealthCheck": "0.1.1-draft"},
            build={},
            endpoint="/version",
        )
