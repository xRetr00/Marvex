from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.assistant_runtime.input_normalization import build_text_input_event, build_turn_input_from_event
from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.contracts import ErrorCode, ErrorEnvelope, FinishReason, ProviderRequest, ProviderResponse
from packages.telemetry import InMemoryTraceReader
from services.core.main import (
    _CoreServiceProviderWorkerTurnExecutor,
    _approved_tool_continuation_messages,
    _required_tool_call_repair_prompt,
    _tool_failure_retry_guidance,
)


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


class _BrowserIntentClassifier:
    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": "intent.browser_computer_use",
                    "intent_kind": "browser_computer_use",
                },
                "confidence_bucket": "high",
                "risk_signal": "none",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


class _WebSearchIntentClassifier:
    def classify(self, turn_input: Any) -> dict[str, Any]:
        return {
            "backend_name": "test.fixed",
            "classification": {
                "schema_version": turn_input.schema_version,
                "trace_id": turn_input.trace_id,
                "turn_id": turn_input.turn_id,
                "selected_intent": {
                    "intent_id": "intent.web_search",
                    "intent_kind": "web_search",
                },
                "confidence_bucket": "high",
                "risk_signal": "none",
                "clarification_needed": "not_needed",
                "route_reason_code": "test.fixed",
                "raw_input_persisted": False,
            },
        }


class _ProviderWebSearchNoEvidence:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if request.tool_messages:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="fake",
                response_id="resp-web-final",
                output_text="I found search results, but none included citeable evidence refs.",
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
            response_id="resp-web-tool",
            output_text="",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
            tool_calls=[
                {
                    "id": "call-web-search",
                    "type": "function",
                    "function": {
                        "name": "web.search",
                        "arguments": '{"query": "latest private unreleased fact"}',
                    },
                }
            ],
        )


class _WebProviderWithoutEvidenceRefs:
    provider_name = "fake-web-no-evidence"

    def search(self, query: Any) -> Any:
        from packages.web_search_runtime import WebSearchGroundingBundle, WebSearchResult

        result = WebSearchResult(
            title="Unciteable result",
            url="https://example.test/no-ref",
            domain="example.test",
            snippet="Search result exists, but no evidence refs were produced.",
        )
        return WebSearchGroundingBundle(query=query, provider=self.provider_name, results=(result,), evidence_refs=())


class _ProviderErrorThenFileWrite:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []
        self.failed_tool_request = False

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if request.tool_messages:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="fake",
                response_id="resp-file-write-final",
                output_text="File update completed.",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
            )
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


class _RecordingPlainProvider:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
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
    assert result.metadata["approved_tool_continuation"]["attempted"] is True
    assert any(request.tool_messages for request in provider.requests)
    assert "approval-turn-auto-marvex-file-write" not in executor._pending_automation


def test_core_request_builder_owner_approves_memory_without_human_gate(tmp_path: Path) -> None:
    provider = _RecordingPlainProvider()
    executor = _executor(tmp_path, provider)
    request_builder = executor._make_tool_request_builder(
        _turn_input(
            "Remember User likes terse answers.",
            trace_id="trace-memory-owner-approved",
            turn_id="turn-memory-owner-approved",
        )
    )

    request = request_builder(
        "memory.remember",
        {"content": "User likes terse answers.", "scope": "session"},
    )

    assert request is not None
    assert request.permission_decision.decision == "approved"
    assert request.permission_decision.reason_code == "policy_owner_approved_memory_tool"
    assert request.permission_decision.human_approval.required is False
    assert request.permission_decision.human_approval.prompt_user_visible is False


def test_browser_intent_tool_catalog_includes_existing_browser_playwright_mcp(tmp_path: Path) -> None:
    provider = _RecordingPlainProvider()
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        file_capability_root=str(tmp_path),
    )
    executor._provider = provider
    executor._intent_classifier = _BrowserIntentClassifier()

    executor.submit_turn(
        _turn_input(
            "Open YouTube",
            trace_id="trace-browser-tool-catalog",
            turn_id="turn-browser-tool-catalog",
        )
    )

    tool_names = {
        str(tool.get("function", {}).get("name") if isinstance(tool.get("function"), dict) else "")
        for request in provider.requests
        for tool in request.tools
        if isinstance(tool, dict)
    }
    assert "builtin.browser_use" in tool_names
    assert "builtin.playwright_browser" in tool_names
    assert "builtin.computer_use" in tool_names
    assert provider.requests
    assert provider.requests[0].provider_options["parallel_tool_calls"] is False


def test_web_search_tool_no_evidence_preserves_model_answer_with_warning(tmp_path: Path) -> None:
    provider = _ProviderWebSearchNoEvidence()
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        file_capability_root=str(tmp_path),
        web_search_provider=_WebProviderWithoutEvidenceRefs(),
    )
    executor._provider = provider
    executor._intent_classifier = _WebSearchIntentClassifier()

    result = executor.submit_turn(
        _turn_input(
            "Search for the latest private unreleased fact",
            trace_id="trace-web-no-evidence-preserve",
            turn_id="turn-web-no-evidence-preserve",
        )
    )

    assert result.error is None
    assert result.assistant_final_response is not None
    assert "I found search results" in result.assistant_final_response.text
    assert "Warning: web search returned no citeable evidence refs." in result.assistant_final_response.text
    assert result.metadata["grounding"]["citation_validation"] == "citation.evidence_missing"


def test_browser_intent_retries_missing_required_tool_call_before_real_failure(tmp_path: Path) -> None:
    provider = _RecordingPlainProvider()
    executor = _CoreServiceProviderWorkerTurnExecutor(
        provider_name="fake",
        model="fake-model",
        trace_reader=InMemoryTraceReader(),
        file_capability_root=str(tmp_path),
        autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX),
    )
    executor._provider = provider
    executor._intent_classifier = _BrowserIntentClassifier()

    result = executor.submit_turn(
        _turn_input(
            "Open YouTube",
            trace_id="trace-browser-missing-tool-retry",
            turn_id="turn-browser-missing-tool-retry",
        )
    )

    tool_requests = [request for request in provider.requests if request.tools]
    assert len(tool_requests) == 5
    assert all("approval" not in request.input_text.lower() for request in tool_requests[1:])
    assert all("Call browser_use, playwright_browser, or computer_use" in request.input_text for request in tool_requests[1:])
    assert result.assistant_final_response is not None
    assert "approval" not in result.assistant_final_response.text.lower()
    assert "did not provide the required tool call" in result.assistant_final_response.text


def test_browser_tool_repair_prompt_offers_browser_tool_alternatives() -> None:
    prompt = _required_tool_call_repair_prompt(
        original_user_input="Open YouTube",
        required_tool_reason="browser_computer_use_tool_required",
    )

    assert "browser_use" in prompt
    assert "computer_use" in prompt
    assert "playwright_browser" in prompt
    assert "try another available browser or desktop tool" in prompt


def test_failed_approved_tool_result_carries_retry_guidance_to_model() -> None:
    turn_input = _turn_input(
        "Open YouTube",
        trace_id="trace-approved-tool-guidance",
        turn_id="turn-approved-tool-guidance",
    )
    pending_tool = {
        "tool_id": "builtin.playwright_browser",
        "capability_id": "playwright_mcp.task",
        "arguments": {"tool_name": "browser_navigate", "tool_args": {"url": "https://youtube.com"}},
        "call_id": "call-browser",
    }
    tool_response = {
        "ok": False,
        "result": {
            "status": "failed",
            "safe_result": {"reason_code": "playwright_mcp_execution_failed:ExceptionGroup"},
        },
    }

    guidance = _tool_failure_retry_guidance(
        turn_input,
        pending_tool=pending_tool,
        tool_response=tool_response,
        attempt=3,
        max_attempts=5,
    )
    messages = _approved_tool_continuation_messages(
        pending_tool,
        tool_response,
        recovery_guidance=guidance,
    )

    assert messages[0]["role"] == "assistant"
    assert messages[1]["role"] == "tool"
    assert messages[1]["tool_call_id"] == "call-browser"
    content = str(messages[1]["content"])
    assert '"attempt": 3' in content
    assert '"max_attempts": 5' in content
    assert "playwright_mcp_execution_failed:ExceptionGroup" in content
    assert "If any other available tool can solve it better" in content
    assert "approval" not in content.lower()
    assert "safely" not in content.lower()
