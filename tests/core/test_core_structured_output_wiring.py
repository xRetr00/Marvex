from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import FinishReason, ProviderRequest, ProviderResponse
from packages.telemetry import InMemoryTraceReader
from services.core.main import _CoreServiceProviderWorkerTurnExecutor


class _JsonProvider:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="fake",
            response_id=f"{request.turn_id}:json-provider",
            output_text=self.output_text,
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )


class _FixedIntentClassifier:
    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": "intent.memory",
                    "intent_kind": "memory",
                },
                "confidence_bucket": "high",
                "risk_signal": "none",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


def _turn_input(text: str) -> Any:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-structured",
        event_id="turn-core-structured:input",
        text=text,
        timestamp=datetime.now(UTC),
        session_id="session-core-structured",
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-structured",
        turn_id="turn-core-structured",
        input_event=event,
    )


def _assistant_final_response_json(text: str) -> str:
    return json.dumps(
        {
            "schema_version": "0.1.1-draft",
            "response_type": "text",
            "text": text,
            "payload_ref": None,
            "output_channel_intent": "default",
            "safe_for_display": True,
            "safe_for_speech": True,
            "memory_write_candidate_hint": False,
            "finish_reason": "stop",
            "metadata": {},
        }
    )


def _executor(provider: _JsonProvider) -> _CoreServiceProviderWorkerTurnExecutor:
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
    )
    executor._provider = provider
    executor._intent_classifier = _FixedIntentClassifier()
    return executor


def test_core_memory_provider_answer_consumes_valid_structured_output() -> None:
    provider = _JsonProvider(_assistant_final_response_json("Structured memory answer."))

    result = _executor(provider).submit_turn(_turn_input("Use memory context."))

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Structured memory answer."
    structured = result.metadata["structured_output"]
    assert structured["requested"] is True
    assert structured["state"] == "valid_structured_result"
    assert structured["validated"] is True
    assert "Structured memory answer" not in json.dumps(result.metadata)


def test_core_memory_provider_answer_falls_back_when_structured_output_invalid() -> None:
    raw_output = "not-json-with-unsafe-provider-shape"
    provider = _JsonProvider(raw_output)

    result = _executor(provider).submit_turn(_turn_input("Use memory context."))

    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == (
        "Provider output could not be validated as structured data."
    )
    structured = result.metadata["structured_output"]
    assert structured["requested"] is True
    assert structured["state"] == "invalid_structured_output"
    assert structured["validated"] is False
    assert raw_output not in result.model_dump_json()
