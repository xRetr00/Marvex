from __future__ import annotations

# file size justification: the approved Core service entrypoint is constrained by
# service placeholder gates to this file, so local IPC composition helpers live
# here until a later approved service split expands the allowed file set.

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from wsgiref.simple_server import make_server

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantResponseType,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    OutputChannelIntent,
    ProviderRequest,
    ProviderResponse,
    StageStatus,
    StageSummary,
    ToolResultRef,
)
from packages.core import CoreService
from packages.core.orchestration.assistant_provider_stage import (
    run_assistant_provider_stage_turn,
)
from packages.local_api import LocalApiConfig, create_health_version_api_app
from packages.local_api.health_version_api import LOCAL_TURNS_EXECUTION_MODE
from packages.telemetry import InMemoryTraceReader


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_FOUNDATION_MODEL = "fake-model"
DEFAULT_PROVIDER = "fake"
STARTUP_MESSAGE_PREFIX = "Core service startup metadata: "

ServerFactory = Callable[[str, int, Any], Any]


@dataclass(frozen=True)
class CoreServiceEntrypointConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    local_auth_token: str | None = None
    foundation_model: str = DEFAULT_FOUNDATION_MODEL
    provider: str = DEFAULT_PROVIDER
    worker_provider: str | None = None
    base_url: str | None = None
    timeout_seconds: float | None = None
    allow_remote: bool = False

    def local_api_config(self) -> LocalApiConfig:
        return LocalApiConfig(
            host=self.host,
            port=self.port,
            allow_remote=self.allow_remote,
        )


@dataclass(frozen=True)
class _CoreTurnExecutorRequest:
    schema_version: str
    execution_mode: str
    assistant_turn_input: Any
    model: str
    instructions: str | None
    previous_response_id: str | None
    provider_options: dict[str, object]


class _CoreServiceFoundationTurnExecutor:
    def __init__(
        self,
        *,
        foundation_turn_handler: Callable[[_CoreTurnExecutorRequest], Any],
        model: str,
    ) -> None:
        self._foundation_turn_handler = foundation_turn_handler
        self._model = model

    def submit_turn(self, turn_input):
        return self._foundation_turn_handler(
            _CoreTurnExecutorRequest(
                schema_version=turn_input.schema_version,
                execution_mode=LOCAL_TURNS_EXECUTION_MODE,
                assistant_turn_input=turn_input,
                model=self._model,
                instructions=None,
                previous_response_id=None,
                provider_options={},
            )
        )


class _ProviderWorkerProcessProvider:
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._provider_name = provider_name
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._python_executable = python_executable

    def send(self, request: ProviderRequest) -> ProviderResponse:
        send_command: dict[str, object] = {
            "command": "send",
            "trace_id": request.trace_id,
            "provider_name": self._provider_name,
            "request": request.model_dump(mode="json"),
        }
        if self._base_url is not None:
            send_command["base_url"] = self._base_url
        if self._timeout_seconds is not None:
            send_command["timeout_seconds"] = self._timeout_seconds
        stop_command = {"command": "stop", "trace_id": request.trace_id}
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.provider_worker.main",
                "--jsonl",
            ],
            input=json.dumps(send_command) + "\n" + json.dumps(stop_command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            raise ConnectionError("ProviderWorker process unavailable.")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("ProviderWorker returned no response.")
        payload = json.loads(lines[0])
        if isinstance(payload, dict) and payload.get("response") is not None:
            return ProviderResponse.model_validate(payload["response"])
        if isinstance(payload, dict) and payload.get("error") is not None:
            error = ErrorEnvelope.model_validate(payload["error"])
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name=self._provider_name,
                response_id=None,
                output_text="",
                finish_reason=FinishReason.ERROR,
                usage={},
                raw_metadata={},
                error=error,
            )
        raise RuntimeError("ProviderWorker response was invalid.")


class _IntentWorkerProcessClassifier:
    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._python_executable = python_executable

    def classify(self, turn_input: AssistantTurnInput) -> dict[str, object]:
        command = {
            "command": "classify",
            "trace_id": turn_input.trace_id,
            "turn_id": turn_input.turn_id,
            "user_input_summary": turn_input.user_visible_input or "",
        }
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.intent_worker.main",
                "--jsonl",
            ],
            input=json.dumps(command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            raise ConnectionError("IntentWorker process unavailable.")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("IntentWorker returned no response.")
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or payload.get("classification") is None:
            raise RuntimeError("IntentWorker response was invalid.")
        return payload


class _ToolWorkerProcessExecutor:
    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._python_executable = python_executable

    def execute(
        self,
        turn_input: AssistantTurnInput,
        *,
        action: str,
        capability: str,
        resource_type: str,
    ) -> dict[str, object]:
        command = {
            "command": "execute",
            "trace_id": turn_input.trace_id,
            "turn_id": turn_input.turn_id,
            "capability_id": "fake.status",
            "action": action,
            "capability": capability,
            "resource_type": resource_type,
            "arguments": {"input_present": bool(turn_input.user_visible_input)},
        }
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.tool_worker.main",
                "--jsonl",
            ],
            input=json.dumps(command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            raise ConnectionError("ToolWorker process unavailable.")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("ToolWorker returned no response.")
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or payload.get("result") is None:
            raise RuntimeError("ToolWorker response was invalid.")
        return payload


class _CoreServiceProviderWorkerTurnExecutor:
    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._provider = _ProviderWorkerProcessProvider(
            provider_name=provider_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        self._intent_classifier = _IntentWorkerProcessClassifier(
            timeout_seconds=timeout_seconds,
        )
        self._tool_executor = _ToolWorkerProcessExecutor(
            timeout_seconds=timeout_seconds,
        )
        self._model = model

    def submit_turn(self, turn_input: AssistantTurnInput) -> AssistantTurnResult:
        try:
            intent_response = self._intent_classifier.classify(turn_input)
        except Exception:
            return _entrypoint_error_result(
                turn_input,
                reason="intent_worker_unavailable",
                message="Intent classification failed.",
            )
        intent_projection = dict(intent_response["classification"])
        intent_kind = str(
            dict(intent_projection.get("selected_intent", {})).get("intent_kind", "")
        )
        metadata: dict[str, object] = {
            "intent_boundary": "intent_worker_process",
            "intent": intent_projection,
            "intent_backend": intent_response.get("backend_name"),
        }
        if intent_projection.get("clarification_needed") == "needed" or intent_kind == "clarification":
            return _entrypoint_text_result(
                turn_input,
                text="I need clarification before continuing.",
                metadata=metadata,
                stage_name="intent_preflight",
            )
        if intent_projection.get("risk_signal") == "unsafe_request" or intent_kind in {
            "unsafe_or_injection_suspected",
            "unsafe_risky",
        }:
            return _entrypoint_error_result(
                turn_input,
                reason="unsafe_intent_blocked",
                message="Request blocked by intent safety preflight.",
                metadata=metadata,
            )
        if intent_kind == "capability_tool":
            return self._run_tool_path(
                turn_input,
                metadata=metadata,
                action="read",
                capability="read",
                resource_type="local_status",
            )
        if intent_kind == "risky_action":
            return self._run_tool_path(
                turn_input,
                metadata=metadata,
                action="delete local file",
                capability="file_delete",
                resource_type="file",
            )

        result = run_assistant_provider_stage_turn(
            turn_input,
            provider=self._provider,
            model=self._model,
        )
        metadata = dict(result.metadata)
        metadata.update(
            {
                "intent_boundary": "intent_worker_process",
                "intent": intent_projection,
                "intent_backend": intent_response.get("backend_name"),
            }
        )
        metadata["provider_boundary"] = "provider_worker_process"
        return result.model_copy(update={"metadata": metadata})

    def _run_tool_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        action: str,
        capability: str,
        resource_type: str,
    ) -> AssistantTurnResult:
        try:
            tool_response = self._tool_executor.execute(
                turn_input,
                action=action,
                capability=capability,
                resource_type=resource_type,
            )
        except Exception:
            return _entrypoint_error_result(
                turn_input,
                reason="tool_worker_unavailable",
                message="Tool execution failed.",
                metadata=metadata,
            )
        combined_metadata = dict(metadata)
        combined_metadata["tool_boundary"] = "tool_worker_process"
        combined_metadata["tool"] = tool_response
        if tool_response.get("ok") is not True:
            return _entrypoint_error_result(
                turn_input,
                reason="tool_execution_blocked",
                message="Capability execution blocked by policy.",
                metadata=combined_metadata,
            )
        return _entrypoint_text_result(
            turn_input,
            text="Capability completed.",
            metadata=combined_metadata,
            stage_name="tool_execution",
            tool_result_refs=[
                ToolResultRef(
                    ref_type="tool_result",
                    ref_id=f"{turn_input.turn_id}:capability:result",
                )
            ],
        )


class _HealthOnlyTurnExecutor:
    def submit_turn(self, turn_input):
        return AssistantTurnResult(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            assistant_final_response=None,
            output_events=[],
            stage_summaries=[],
            provider_turn_refs=[],
            tool_result_refs=[],
            memory_result_refs=[],
            session_result_ref=None,
            error=ErrorEnvelope(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                error_id=f"{turn_input.turn_id}:core-service:turn-executor-unavailable",
                code=ErrorCode.SERVICE_UNHEALTHY,
                message="Core service turn executor is unavailable in health-only mode.",
                recoverable=True,
                source="core_service_entrypoint",
                details={"reason": "health_only_mode"},
            ),
            metadata={},
        )


def _entrypoint_text_result(
    turn_input: AssistantTurnInput,
    *,
    text: str,
    metadata: dict[str, object],
    stage_name: str,
    tool_result_refs: list[ToolResultRef] | None = None,
) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=AssistantFinalResponse(
            schema_version=turn_input.schema_version,
            response_type=AssistantResponseType.TEXT,
            text=text,
            payload_ref=None,
            output_channel_intent=OutputChannelIntent.DEFAULT,
            safe_for_display=True,
            safe_for_speech=True,
            memory_write_candidate_hint=False,
            finish_reason=AssistantFinishReason.STOP,
            metadata={},
        ),
        output_events=[],
        stage_summaries=[
            _stage_summary("input_normalization", StageStatus.COMPLETED),
            _stage_summary(stage_name, StageStatus.COMPLETED),
            _stage_summary("final_response_assembly", StageStatus.COMPLETED),
        ],
        provider_turn_refs=[],
        tool_result_refs=list(tool_result_refs or []),
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata=metadata,
    )


def _entrypoint_error_result(
    turn_input: AssistantTurnInput,
    *,
    reason: str,
    message: str,
    metadata: dict[str, object] | None = None,
) -> AssistantTurnResult:
    error_id = f"{turn_input.turn_id}:core-service-entrypoint:{reason}"
    return AssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=None,
        output_events=[],
        stage_summaries=[
            _stage_summary("input_normalization", StageStatus.COMPLETED),
            _stage_summary("intent_preflight", StageStatus.FAILED, error_ref=error_id),
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=ErrorEnvelope(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            error_id=error_id,
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            recoverable=False,
            source="core_service_entrypoint",
            details={"reason": reason},
        ),
        metadata=dict(metadata or {}),
    )


def _stage_summary(
    stage_name: str,
    status: StageStatus,
    *,
    error_ref: str | None = None,
) -> StageSummary:
    return StageSummary(
        stage_name=stage_name,
        status=status,
        started_at=None,
        completed_at=None,
        ref=None,
        error_ref=error_ref,
    )


def _create_foundation_turn_executor(
    *,
    trace_reader: InMemoryTraceReader,
) -> _CoreServiceFoundationTurnExecutor:
    from packages.runtime_composition import create_local_api_fake_turn_handler

    return _CoreServiceFoundationTurnExecutor(
        foundation_turn_handler=create_local_api_fake_turn_handler(
            telemetry_sink=trace_reader
        ),
        model=DEFAULT_FOUNDATION_MODEL,
    )


def create_core_service(
    *,
    trace_reader: InMemoryTraceReader | None = None,
    enable_foundation_turns: bool = True,
    config: CoreServiceEntrypointConfig | None = None,
) -> CoreService:
    effective_trace_reader = trace_reader or InMemoryTraceReader()
    effective_config = config or CoreServiceEntrypointConfig()
    executor = (
        _create_turn_executor(
            trace_reader=effective_trace_reader,
            config=effective_config,
        )
        if enable_foundation_turns
        else _HealthOnlyTurnExecutor()
    )
    return CoreService(turn_executor=executor)


def _create_turn_executor(
    *,
    trace_reader: InMemoryTraceReader,
    config: CoreServiceEntrypointConfig,
) -> object:
    if config.provider == "fake":
        return _create_foundation_turn_executor(trace_reader=trace_reader)
    provider_name = (
        config.worker_provider
        if config.provider == "provider_worker"
        else config.provider
    )
    return _CoreServiceProviderWorkerTurnExecutor(
        provider_name=provider_name or "fake",
        model=config.foundation_model,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    )


def create_core_service_app(
    *,
    config: CoreServiceEntrypointConfig,
    trace_reader: InMemoryTraceReader | None = None,
) -> tuple[Any, CoreService]:
    service = create_core_service(trace_reader=trace_reader, config=config)
    service.start()
    app = create_health_version_api_app(
        service,
        turn_handler=lambda request: service.submit_turn(request.assistant_turn_input),
        trace_reader=trace_reader,
        local_auth_token=config.local_auth_token,
    )
    return app, service


def health_once_payload() -> dict[str, object]:
    service = create_core_service(enable_foundation_turns=False)
    service.start()
    try:
        return {
            "health": service.get_health().model_dump(mode="json"),
            "version": service.get_version().model_dump(mode="json"),
        }
    finally:
        service.shutdown()


def run_health_once() -> int:
    print(json.dumps(health_once_payload(), sort_keys=True))
    return 0


def run_core_service(
    *,
    config: CoreServiceEntrypointConfig | None = None,
    server_factory: ServerFactory = make_server,
) -> int:
    effective_config = config or CoreServiceEntrypointConfig()
    if not effective_config.allow_remote:
        _validate_loopback(effective_config.host)
    local_api_config = effective_config.local_api_config()
    if not effective_config.local_auth_token or not effective_config.local_auth_token.strip():
        raise ValueError("local_auth_token is required for Core service startup")

    trace_reader = InMemoryTraceReader()
    app, service = create_core_service_app(
        config=effective_config,
        trace_reader=trace_reader,
    )
    httpd = server_factory(local_api_config.host, local_api_config.port, app)
    print(
        STARTUP_MESSAGE_PREFIX
        + json.dumps(
            {
                "base_url": f"http://{local_api_config.host}:{local_api_config.port}",
                "auth_required": True,
                "auth_token_present": True,
                "token_value_logged": False,
                "service": "marvex-core-service",
                "provider": effective_config.provider,
            },
            sort_keys=True,
        )
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.shutdown()
        httpd.server_close()
    return 0


def run_turn_once(
    *,
    text: str,
    config: CoreServiceEntrypointConfig,
    trace_id: str,
    turn_id: str,
) -> int:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        event_id=f"{turn_id}:input",
        text=text,
        timestamp=datetime.now(UTC),
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id=turn_id,
        input_event=event,
    )
    service = create_core_service(config=config)
    service.start()
    try:
        result = service.submit_turn(turn_input)
    finally:
        service.shutdown()
    print(result.model_dump_json())
    return 0


def _validate_loopback(host: str) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("host must be loopback-only")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Core service local entrypoint. Defaults to loopback 127.0.0.1; "
            "pass --allow-remote to bind a non-loopback host (bearer auth required)."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--health-once",
        action="store_true",
        help="Start CoreService in-process, print health/version JSON, then shut down.",
    )
    mode.add_argument(
        "--serve",
        action="store_true",
        help="Start the local Core service API on 127.0.0.1.",
    )
    mode.add_argument(
        "--turn-once",
        metavar="TEXT",
        help="Run one local Core turn and print an AssistantTurnResult JSON envelope.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Bind host. Defaults to 127.0.0.1. Use --allow-remote for non-loopback.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit binding a non-loopback host. Requires --local-auth-token.",
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        type=int,
        help="Loopback bind port. Defaults to 8765.",
    )
    parser.add_argument(
        "--local-auth-token",
        default=None,
        help="Bearer token required for protected local Core service endpoints.",
    )
    parser.add_argument(
        "--provider",
        choices=("fake", "lmstudio_responses", "litellm", "provider_worker"),
        default=DEFAULT_PROVIDER,
        help="Provider selection for turn execution. Defaults to fake.",
    )
    parser.add_argument(
        "--worker-provider",
        default=None,
        help="ProviderWorker target provider when --provider provider_worker is used.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_FOUNDATION_MODEL,
        help="Model name to place on provider requests.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL for local provider-compatible endpoints.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Provider request timeout in seconds.",
    )
    parser.add_argument(
        "--trace-id",
        default="trace-core-provider-worker-turn-once",
        help="Trace id for --turn-once.",
    )
    parser.add_argument(
        "--turn-id",
        default="turn-core-provider-worker-turn-once",
        help="Turn id for --turn-once.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.health_once:
        return run_health_once()
    config = CoreServiceEntrypointConfig(
        host=args.host,
        port=args.port,
        local_auth_token=args.local_auth_token,
        foundation_model=args.model,
        provider=args.provider,
        worker_provider=args.worker_provider,
        base_url=args.base_url,
        timeout_seconds=args.timeout,
        allow_remote=args.allow_remote,
    )
    if args.turn_once is not None:
        return run_turn_once(
            text=args.turn_once,
            config=config,
            trace_id=args.trace_id,
            turn_id=args.turn_id,
        )
    try:
        return run_core_service(
            config=config
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
