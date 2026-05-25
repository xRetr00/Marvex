from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantMode,
    AssistantResponseType,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    HealthCheck,
    HealthStatus,
    OutputChannelIntent,
    PolicyContext,
    Sensitivity,
    VersionInfo,
)
from tests.local_api.asgi_helpers import asgi_call


SCHEMA_VERSION = "0.1.1-draft"
EXPECTED_TOKEN = "fake-core-local-token"


def make_turn_input(
    *,
    schema_version: str = SCHEMA_VERSION,
    trace_id: str = "trace-core-service",
    turn_id: str = "turn-core-service",
) -> AssistantTurnInput:
    return AssistantTurnInput(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        input_event_id="event-core-service",
        session_ref=None,
        identity_ref=None,
        user_visible_input="Hello through CoreService",
        assistant_mode=AssistantMode.DEFAULT,
        policy_context=PolicyContext(
            requested_capabilities=[],
            sensitivity=Sensitivity.NORMAL,
        ),
        metadata={},
    )


def make_success_result(turn_input: AssistantTurnInput) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=AssistantFinalResponse(
            schema_version=turn_input.schema_version,
            response_type=AssistantResponseType.TEXT,
            text="CoreService handled the turn.",
            payload_ref=None,
            output_channel_intent=OutputChannelIntent.DEFAULT,
            safe_for_display=True,
            safe_for_speech=True,
            memory_write_candidate_hint=False,
            finish_reason=AssistantFinishReason.STOP,
            metadata={},
        ),
        output_events=[],
        stage_summaries=[],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={"handled_by": "test_executor"},
    )


class RecordingTurnExecutor:
    def __init__(self) -> None:
        self.turns: list[AssistantTurnInput] = []

    def submit_turn(self, turn_input: AssistantTurnInput) -> AssistantTurnResult:
        self.turns.append(turn_input)
        return make_success_result(turn_input)


class ExplodingTurnExecutor:
    def submit_turn(self, _turn_input: AssistantTurnInput) -> AssistantTurnResult:
        raise RuntimeError("raw executor failure with secret detail")


class MismatchedTurnExecutor:
    def submit_turn(self, turn_input: AssistantTurnInput) -> AssistantTurnResult:
        return make_success_result(turn_input).model_copy(
            update={"trace_id": "trace-from-wrong-turn"}
        )


def make_service(executor=None):
    from packages.core import CoreService

    started_at = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    return CoreService(
        turn_executor=executor or RecordingTurnExecutor(),
        started_at=started_at,
        clock=lambda: started_at + timedelta(seconds=12),
    )


def test_core_service_health_and_version_use_approved_contracts():
    service = make_service()

    starting_health = HealthCheck.model_validate(service.get_health().model_dump())
    started_health = HealthCheck.model_validate(service.start().model_dump())
    version = VersionInfo.model_validate(service.get_version().model_dump())

    assert starting_health.schema_version == SCHEMA_VERSION
    assert starting_health.service == "marvex-core-service"
    assert starting_health.status == HealthStatus.STARTING
    assert started_health.status == HealthStatus.OK
    assert started_health.dependencies == {
        "turn_executor": {"configured": True},
        "accepting_turns": True,
    }
    assert started_health.uptime_seconds == 12
    assert version.service == "marvex-core-service"
    assert version.contract_versions == {
        "CoreService": SCHEMA_VERSION,
        "AssistantTurnInput": SCHEMA_VERSION,
        "AssistantTurnResult": SCHEMA_VERSION,
        "ErrorEnvelope": SCHEMA_VERSION,
        "HealthCheck": SCHEMA_VERSION,
        "VersionInfo": SCHEMA_VERSION,
    }


def test_core_service_lifecycle_rejects_turns_until_started_and_after_shutdown():
    service = make_service()
    turn_input = make_turn_input()

    before_start = service.submit_turn(turn_input)
    shutdown_health = service.shutdown()
    after_shutdown = service.submit_turn(turn_input)

    assert shutdown_health.status == HealthStatus.STOPPING
    for result, reason in [
        (before_start, "service_not_started"),
        (after_shutdown, "service_shutting_down"),
    ]:
        assert result.assistant_final_response is None
        assert result.trace_id == turn_input.trace_id
        assert result.turn_id == turn_input.turn_id
        assert result.error is not None
        assert result.error.code == ErrorCode.SERVICE_UNHEALTHY
        assert result.error.source == "core_service"
        assert result.error.details == {"reason": reason}


def test_core_service_turn_submission_delegates_to_injected_executor():
    executor = RecordingTurnExecutor()
    service = make_service(executor)
    turn_input = make_turn_input()

    service.start()
    result = AssistantTurnResult.model_validate(
        service.submit_turn(turn_input).model_dump()
    )

    assert result.error is None
    assert result.trace_id == "trace-core-service"
    assert result.turn_id == "turn-core-service"
    assert result.assistant_final_response.text == "CoreService handled the turn."
    assert executor.turns == [turn_input]


def test_core_service_executor_exception_returns_safe_error_envelope():
    service = make_service(ExplodingTurnExecutor())
    turn_input = make_turn_input()

    service.start()
    result = service.submit_turn(turn_input)
    serialized = json.dumps(result.model_dump(mode="json"))

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.INTERNAL_ERROR
    assert result.error.message == "CoreService turn execution failed."
    assert result.error.details == {"reason": "turn_executor_failure"}
    assert "raw executor failure" not in serialized
    assert "secret detail" not in serialized


def test_core_service_enforces_result_trace_and_turn_identity():
    service = make_service(MismatchedTurnExecutor())
    turn_input = make_turn_input()

    service.start()
    result = service.submit_turn(turn_input)

    assert result.assistant_final_response is None
    assert result.schema_version == turn_input.schema_version
    assert result.trace_id == turn_input.trace_id
    assert result.turn_id == turn_input.turn_id
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.details == {"reason": "result_envelope_mismatch"}


def test_core_service_contract_validation_requires_schema_trace_and_turn_ids():
    for field in ["schema_version", "trace_id", "turn_id"]:
        values = make_turn_input().model_dump()
        values[field] = ""

        with pytest.raises(ValueError):
            AssistantTurnInput.model_validate(values)


def call_app(
    app,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    auth: str | None = None,
) -> tuple[str, dict]:
    status, _headers, payload = asgi_call(app, path, method=method, body=body, auth=auth)
    return status, payload


def local_api_payload(turn_input: AssistantTurnInput) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": turn_input.model_dump(mode="json"),
        "model": "fake-model",
        "instructions": None,
        "previous_response_id": None,
        "provider_options": {},
    }


def test_core_service_composes_with_existing_loopback_local_api_turn_path():
    from packages.local_api import LocalApiConfig, create_local_api_asgi_app

    service = make_service()
    service.start()
    app = create_local_api_asgi_app(
        service,
        turn_handler=lambda request: service.submit_turn(request.assistant_turn_input),
        local_auth_token=EXPECTED_TOKEN,
    )

    health_status, health_payload = call_app(app, "/health")
    version_status, version_payload = call_app(app, "/version")
    turn_status, turn_payload = call_app(
        app,
        "/v1/turns",
        method="POST",
        body=local_api_payload(make_turn_input()),
        auth=f"Bearer {EXPECTED_TOKEN}",
    )

    assert LocalApiConfig().host == "127.0.0.1"
    with pytest.raises(ValueError, match="loopback-only"):
        LocalApiConfig(host="0.0.0.0")
    assert health_status == "200 OK"
    assert HealthCheck.model_validate(health_payload).service == "marvex-core-service"
    assert version_status == "200 OK"
    assert VersionInfo.model_validate(version_payload).service == "marvex-core-service"
    assert turn_status == "200 OK"
    result = AssistantTurnResult.model_validate(turn_payload)
    assert result.trace_id == "trace-core-service"
    assert result.error is None


def test_core_service_source_has_no_forbidden_boundary_imports_or_tokens():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((Path("packages") / "core").rglob("*.py"))
    )
    lowered = source.lower()
    forbidden = [
        "packages.adapters",
        "packages.provider_runtime",
        "packages.voice_worker_runtime",
        "packages.voice_runtime",
        "packages.local_api",
        "packages.runtime_composition",
        "lmstudio",
        "litellm",
        "openai",
        "anthropic",
        "gemini",
        "0.0.0.0",
        "socket",
        "subprocess",
        "packages.memory",
        "memory_runtime",
        "desktop",
        "proactive",
    ]

    assert [token for token in forbidden if token in lowered] == []
