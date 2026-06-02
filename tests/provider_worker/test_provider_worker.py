from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from packages.contracts import ErrorCode, FinishReason, ProviderRequest, ProviderResponse


ROOT = Path(__file__).resolve().parents[2]


def make_request(*, trace_id: str = "trace-provider-worker") -> ProviderRequest:
    return ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id="turn-provider-worker",
        model="fake-model",
        input_text="Hello worker",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )


def run_worker_jsonl(commands: list[dict[str, object]]) -> list[dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, "-m", "services.provider_worker.main", "--jsonl"],
        cwd=ROOT,
        input="".join(json.dumps(command) + "\n" for command in commands),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    return [json.loads(line) for line in completed.stdout.splitlines()]


def test_provider_worker_is_no_longer_readme_only():
    entries = {path.name for path in (ROOT / "services" / "provider_worker").iterdir()}

    assert {"README.md", "__init__.py", "models.py", "controller.py", "main.py"}.issubset(
        entries
    )


def test_provider_worker_entrypoint_help_health_and_version_are_runnable():
    help_result = subprocess.run(
        [sys.executable, "-m", "services.provider_worker.main", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    health_result = subprocess.run(
        [sys.executable, "-m", "services.provider_worker.main", "--health-once"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    version_result = subprocess.run(
        [sys.executable, "-m", "services.provider_worker.main", "--version-once"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "--jsonl" in help_result.stdout
    assert "--health-once" in help_result.stdout
    assert health_result.returncode == 0, health_result.stdout + health_result.stderr
    assert version_result.returncode == 0, version_result.stdout + version_result.stderr
    assert json.loads(health_result.stdout)["service"] == "marvex-provider-worker"
    assert json.loads(version_result.stdout)["service"] == "marvex-provider-worker"


def test_provider_worker_jsonl_start_status_send_and_stop_fake_provider():
    request = make_request(trace_id="trace-worker-jsonl")

    responses = run_worker_jsonl(
        [
            {"command": "start", "trace_id": "trace-worker-jsonl"},
            {"command": "status", "trace_id": "trace-worker-jsonl"},
            {
                "command": "send",
                "trace_id": "trace-worker-jsonl",
                "provider_name": "fake",
                "request": request.model_dump(mode="json"),
            },
            {"command": "stop", "trace_id": "trace-worker-jsonl"},
        ]
    )

    assert [response["command"] for response in responses] == [
        "start",
        "status",
        "send",
        "stop",
    ]
    assert all(response["ok"] is True for response in responses)
    provider_response = ProviderResponse.model_validate(responses[2]["response"])
    assert provider_response.trace_id == "trace-worker-jsonl"
    assert provider_response.provider_name == "fake"
    assert provider_response.output_text == "fake provider response"
    assert provider_response.error is None


def test_provider_worker_ignores_network_timeout_for_fake_provider():
    from services.provider_worker.controller import ProviderWorkerController
    from services.provider_worker.models import ProviderWorkerConfig
    from services.provider_worker.models import ProviderWorkerConfig

    result = ProviderWorkerController(
        config=ProviderWorkerConfig(
            provider_candidates=("fake",),
            fallback_enabled=False,
        )
    ).send(
        provider_name="fake",
        request=make_request().model_copy(
            update={"provider_options": {"grounded_citation_ids": ["web.evidence.1"]}}
        ),
        timeout_seconds=10,
    )

    assert result.ok is True
    assert result.response is not None
    assert result.response.output_text == "Answer from provided evidence [web.evidence.1]."


def test_provider_worker_unsupported_provider_returns_structured_error():
    responses = run_worker_jsonl(
        [
            {
                "command": "send",
                "trace_id": "trace-worker-unsupported",
                "provider_name": "unknown",
                "request": make_request(
                    trace_id="trace-worker-unsupported"
                ).model_dump(mode="json"),
            }
        ]
    )

    assert responses[0]["ok"] is False
    error = responses[0]["error"]
    assert error["trace_id"] == "trace-worker-unsupported"
    assert error["code"] == ErrorCode.PROVIDER_UNAVAILABLE.value
    assert error["details"]["reason"] == "provider_unavailable"
    assert "unsupported provider" not in json.dumps(error).lower()


def test_provider_worker_maps_timeout_and_unavailable_failures():
    from services.provider_worker.controller import ProviderWorkerController

    class TimeoutProvider:
        def send(self, _request: ProviderRequest) -> ProviderResponse:
            raise TimeoutError("secret timeout detail")

    class UnavailableProvider:
        def send(self, _request: ProviderRequest) -> ProviderResponse:
            raise ConnectionError("secret connection detail")

    timeout = ProviderWorkerController(provider_factory=lambda _config: TimeoutProvider())
    unavailable = ProviderWorkerController(
        provider_factory=lambda _config: UnavailableProvider()
    )

    timeout_result = timeout.send(provider_name="fake", request=make_request())
    unavailable_result = unavailable.send(provider_name="fake", request=make_request())
    serialized = json.dumps(
        [timeout_result.model_dump(mode="json"), unavailable_result.model_dump(mode="json")]
    )

    assert timeout_result.error is not None
    assert timeout_result.error.code == ErrorCode.PROVIDER_TIMEOUT
    assert unavailable_result.error is not None
    assert unavailable_result.error.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert "secret" not in serialized


def test_provider_worker_treats_model_tool_call_response_as_success():
    from services.provider_worker.controller import ProviderWorkerController

    class ToolCallProvider:
        def send(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="tool-provider",
                response_id="tool-response",
                output_text="",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
                tool_calls=[
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "builtin.browser_use",
                            "arguments": '{"task": "open example.com"}',
                        },
                    }
                ],
            )

    result = ProviderWorkerController(provider_factory=lambda _config: ToolCallProvider()).send(
        provider_name="litellm",
        request=make_request(),
    )

    assert result.ok is True
    assert result.response is not None
    assert result.response.tool_calls is not None
    assert result.response.tool_calls[0]["function"]["name"] == "builtin.browser_use"


def test_provider_worker_executes_retry_and_fallback_with_selection_runtime():
    from services.provider_worker.controller import ProviderWorkerController
    from services.provider_worker.models import ProviderWorkerConfig

    attempts: list[str] = []

    class ErrorProvider:
        def send(self, request: ProviderRequest) -> ProviderResponse:
            attempts.append("primary")
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="primary",
                response_id=None,
                output_text="",
                finish_reason=FinishReason.ERROR,
                usage={},
                raw_metadata={"raw_payload": "must-not-leak"},
                error=None,
            )

    class SuccessProvider:
        def send(self, request: ProviderRequest) -> ProviderResponse:
            attempts.append("backup")
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="backup",
                response_id="backup-response",
                output_text="fallback response",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={"raw_payload": "must-not-leak"},
                error=None,
            )

    def factory(config):
        if config.provider_name == "primary":
            return ErrorProvider()
        if config.provider_name == "backup":
            return SuccessProvider()
        raise ValueError("unsupported")

    controller = ProviderWorkerController(
        config=ProviderWorkerConfig(
            provider_candidates=("primary", "backup"),
            fallback_enabled=True,
            max_retries=1,
        ),
        provider_factory=factory,
    )

    result = controller.send(provider_name="primary", request=make_request())

    assert result.ok is True
    assert result.response is not None
    assert result.response.provider_name == "backup"
    assert result.response.output_text == "fallback response"
    assert attempts == ["primary", "primary", "backup"]
    assert result.selection is not None
    assert result.selection.selected_provider_id == "primary"
    assert result.selection.fallback_provider_ids == ("backup",)
    assert "must-not-leak" not in result.model_dump_json()


def test_provider_worker_safe_projection_redacts_secrets_and_raw_metadata():
    from services.provider_worker.controller import ProviderWorkerController

    class SecretProvider:
        def send(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="fake",
                response_id="secret-response",
                output_text="safe text",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={
                    "api_key": "must-not-leak",
                    "raw_provider_payload": "must-not-leak",
                    "safe_ref": "kept",
                },
                error=None,
            )

    result = ProviderWorkerController(
        provider_factory=lambda _config: SecretProvider()
    ).send(
        provider_name="fake",
        request=make_request(),
        base_url="http://127.0.0.1:1234/v1",
        timeout_seconds=1,
    )

    dumped = result.model_dump_json()
    assert result.response is not None
    assert result.response.raw_metadata == {"safe_ref": "kept"}
    assert "must-not-leak" not in dumped
    assert "api_key" not in dumped
    assert "raw_provider_payload" not in dumped


def test_provider_worker_passes_litellm_secret_only_to_runtime_config():
    from services.provider_worker.controller import ProviderWorkerController
    from services.provider_worker.models import ProviderWorkerConfig

    captured = {}

    class SecretAwareProvider:
        def send(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="litellm",
                response_id="secret-aware-response",
                output_text="safe text",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
            )

    def provider_factory(config):
        captured["config"] = config
        return SecretAwareProvider()

    result = ProviderWorkerController(
        config=ProviderWorkerConfig(provider_candidates=("litellm",)),
        provider_factory=provider_factory,
    ).send(
        provider_name="litellm",
        request=make_request(),
        litellm_api_key="sk-test-litellm-secret",
    )

    assert result.ok is True
    assert captured["config"].litellm_api_key == "sk-test-litellm-secret"
    assert "sk-test-litellm-secret" not in result.model_dump_json()


def test_provider_worker_does_not_fallback_to_fake_for_concrete_litellm_request():
    from services.provider_worker.controller import ProviderWorkerController

    captured = {}

    class Provider:
        def send(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="litellm",
                response_id="litellm-response",
                output_text="litellm response",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
            )

    def provider_factory(config):
        captured["provider_name"] = config.provider_name
        return Provider()

    result = ProviderWorkerController(provider_factory=provider_factory).send(
        provider_name="litellm",
        request=make_request(),
    )

    assert result.ok is True
    assert captured["provider_name"] == "litellm"
    assert result.selection is not None
    assert result.selection.selected_provider_id == "litellm"
    assert result.selection.fallback_provider_ids == ()


def test_provider_worker_maps_fake_raw_output_to_structured_result_offline():
    payload = {
        "schema_version": "0.1.1-draft",
        "response_type": "text",
        "text": "Validated structured worker response.",
        "payload_ref": None,
        "output_channel_intent": "default",
        "safe_for_display": True,
        "safe_for_speech": True,
        "memory_write_candidate_hint": False,
        "finish_reason": "stop",
        "metadata": {},
    }

    responses = run_worker_jsonl(
        [
            {
                "command": "structured_output",
                "trace_id": "trace-worker-structured",
                "turn_id": "turn-worker-structured",
                "provider_name": "fake",
                "target_contract": "AssistantFinalResponse",
                "raw_output_text": json.dumps(payload),
            }
        ]
    )

    assert responses[0]["command"] == "structured_output"
    assert responses[0]["ok"] is True
    structured = responses[0]["metadata"]["structured_output"]
    assert structured["state"] == "valid_structured_result"
    assert structured["parsed_payload"]["text"] == "Validated structured worker response."
    assert structured["raw_preview"] is None
    assert "raw_output_text" not in json.dumps(responses[0]).lower()
