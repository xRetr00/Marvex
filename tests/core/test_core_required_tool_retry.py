from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.assistant_runtime.input_normalization import build_text_input_event, build_turn_input_from_event
from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.contracts import ErrorCode, ErrorEnvelope, FinishReason, ProviderRequest, ProviderResponse
from packages.telemetry import InMemoryTraceReader
from services.core.main import _CoreServiceProviderWorkerTurnExecutor


class _RiskyIntentClassifier:
    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": "intent.risky_action",
                    "intent_kind": "risky_action",
                },
                "confidence_bucket": "high",
                "risk_signal": "risky_action_requested",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


class _ProviderErrorThenFileWrite:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []
        self.failed_tool_request = False

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if request.tools and not self.failed_tool_request:
            self.failed_tool_request = True
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="fake",
                response_id=None,
                output_text="",
                finish_reason=FinishReason.ERROR,
                usage={},
                raw_metadata={},
                error=ErrorEnvelope(
                    schema_version=request.schema_version,
                    trace_id=request.trace_id,
                    error_id="provider-tool-parse",
                    code=ErrorCode.PROVIDER_ERROR,
                    message="Failed to parse tool call: Unexpected end of content.",
                    recoverable=True,
                    source="test",
                    details={},
                ),
            )
        tool_names = {
            str(tool.get("function", {}).get("name") if isinstance(tool.get("function"), dict) else "")
            for tool in request.tools
            if isinstance(tool, dict)
        }
        if "file.write" not in tool_names:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="fake",
                response_id="resp-plain",
                output_text="plain provider response",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
            )
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="fake",
            response_id="resp-file-write",
            output_text="",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
            tool_calls=[
                {
                    "id": "call-file-write",
                    "type": "function",
                    "function": {
                        "name": "file.write",
                        "arguments": '{"path": "Desktop/Zebra.md", "content": "Zebra notes"}',
                    },
                }
            ],
        )


def _turn_input(text: str, *, trace_id: str, turn_id: str) -> Any:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        event_id=f"{turn_id}:input",
        text=text,
        timestamp=datetime.now(UTC),
        session_id="session-required-tool",
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id=turn_id,
        input_event=event,
    )


def _executor(tmp_path: Path, provider: _ProviderErrorThenFileWrite) -> _CoreServiceProviderWorkerTurnExecutor:
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        file_capability_root=str(tmp_path),
    )
    executor._provider = provider
    executor._intent_classifier = _RiskyIntentClassifier()
    executor._pending_automation_path = tmp_path / "pending-tools.json"
    executor._pending_automation = {}
    return executor


def test_required_file_write_tool_call_provider_error_retries_to_model_tool_approval(tmp_path: Path) -> None:
    provider = _ProviderErrorThenFileWrite()
    executor = _executor(tmp_path, provider)

    result = executor.submit_turn(
        _turn_input(
            "Write File on Desktop Call It Zebra.md And Search About Zebra And Write What You Have Searched There",
            trace_id="trace-required-tool-retry",
            turn_id="turn-required-tool-retry",
        )
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "approval required" in result.assistant_final_response.text.lower()
    tool_requests = [request for request in provider.requests if request.tools]
    assert len(tool_requests) == 2
    assert "previous tool call failed" in tool_requests[1].input_text
    assert result.metadata["approval_request"]["approval_request_id"] == "approval-turn-required-tool-retry"
    assert result.metadata["agentic_tool_loop"]["provider_error_retry"]["attempted"] is True
    assert executor._pending_automation["approval-turn-required-tool-retry"]["capability_id"] == "file.write"


def test_approved_model_file_write_injects_root_and_executes(tmp_path: Path) -> None:
    provider = _ProviderErrorThenFileWrite()
    executor = _executor(tmp_path, provider)
    turn_id = "turn-required-tool-approved"
    approval_id = f"approval-{turn_id}"
    executor._pending_automation[approval_id] = {
        "tool_id": "file.write",
        "capability_id": "file.write",
        "resource_type": "file",
        "capability": "file_write",
        "arguments": {"path": "Desktop/Zebra.md", "content": "Zebra notes"},
        "call_id": "call-file-write",
    }
    (tmp_path / "Desktop").mkdir(parents=True)
    executor._resume_approval = approval_id
    executor._approval_decision = "approve"

    result = executor.submit_turn(
        _turn_input(
            "Write File on Desktop Call It Zebra.md",
            trace_id="trace-required-tool-approved",
            turn_id=turn_id,
        )
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "File update completed" in result.assistant_final_response.text
    assert (tmp_path / "Desktop" / "Zebra.md").read_text(encoding="utf-8") == "Zebra notes"
    assert result.metadata["automation"]["result"]["capability_ref"]["identifier"] == "file.write"


def test_auto_marvex_auto_approves_model_file_write_and_executes(tmp_path: Path) -> None:
    provider = _ProviderErrorThenFileWrite()
    executor = _executor(tmp_path, provider)
    executor._autonomy_policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)
    (tmp_path / "Desktop").mkdir(parents=True)

    result = executor.submit_turn(
        _turn_input(
            "Create Desktop/Zebra.md with content Zebra notes",
            trace_id="trace-auto-marvex-file-write",
            turn_id="turn-auto-marvex-file-write",
        )
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "File update completed" in result.assistant_final_response.text
    assert (tmp_path / "Desktop" / "Zebra.md").read_text(encoding="utf-8") == "Zebra notes"
    assert result.metadata["auto_approval"]["enabled"] is True
    assert result.metadata["approval"]["decision"] == "approved"
    assert "approval-turn-auto-marvex-file-write" not in executor._pending_automation
