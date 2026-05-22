from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from packages.adapters.connectors.github_connector import GITHUB_CONNECTOR_REF, make_fake_fetch_client
from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.connector_runtime.auto_fetch_scheduler import ProviderSyncConfig
from packages.telemetry import InMemoryTraceReader
from services.core.main import (
    _CoreConnectorAutofetchRuntime,
    _CoreServiceProviderWorkerTurnExecutor,
    _enabled_connector_autofetch_policy,
)


class _ConnectorIntentClassifier:
    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": "intent.connector_account",
                    "intent_kind": "connector_account",
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
        trace_id="trace-core-connector-autofetch",
        event_id="turn-core-connector-autofetch:input",
        text=text,
        timestamp=datetime.now(UTC),
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-connector-autofetch",
        turn_id="turn-core-connector-autofetch",
        input_event=event,
    )


def _executor(*, resume: str | None = None, decision: str | None = None) -> _CoreServiceProviderWorkerTurnExecutor:
    runtime = _CoreConnectorAutofetchRuntime(
        connector_ref=GITHUB_CONNECTOR_REF,
        connection_id="github-connector",
        fetch_client=make_fake_fetch_client(
            {None: [("ext-core-1", "Connector Evidence", "Connector auto-fetch memory evidence.")]}
        ),
        provider_config=ProviderSyncConfig(
            connector_id=GITHUB_CONNECTOR_REF.connector_id,
            auto_fetch_enabled=True,
        ),
        policy=_enabled_connector_autofetch_policy(GITHUB_CONNECTOR_REF),
    )
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        resume_approval=resume,
        approval_decision=decision,
        connector_autofetch_runtime=runtime,
    )
    executor._intent_classifier = _ConnectorIntentClassifier()
    return executor


def test_core_connector_autofetch_pauses_before_runtime_sync() -> None:
    result = _executor().submit_turn(_turn_input("sync my GitHub connector"))

    assert result.error is None
    assert result.metadata["agentic_loop"]["stop_reason"] == "waiting_for_human_approval"
    assert result.metadata["connector"]["auto_fetch_enabled"] is True
    assert result.metadata["connector"]["approval_required"] is True
    assert result.metadata["connector"]["live_oauth_started"] is False
    assert result.metadata["connector"]["raw_credentials_persisted"] is False


def test_core_connector_autofetch_resume_approval_syncs_into_memory_tree() -> None:
    result = _executor(
        resume="approval-turn-core-connector-autofetch",
        decision="approve",
    ).submit_turn(_turn_input("sync my GitHub connector"))

    assert result.error is None
    assert result.metadata["agentic_loop"]["executed_count"] >= 1
    assert result.metadata["connector"]["status"] == "synced"
    assert result.metadata["connector"]["documents_canonicalized"] == 1
    assert result.metadata["connector"]["memory_tree_updated"] is True
    assert result.metadata["connector"]["raw_credentials_persisted"] is False
    assert result.metadata["connector"]["raw_payload_persisted"] is False
