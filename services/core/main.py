from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from wsgiref.simple_server import make_server

from packages.contracts import AssistantTurnResult, ErrorCode, ErrorEnvelope
from packages.core import CoreService
from packages.local_api import LocalApiConfig, create_health_version_api_app
from packages.local_api.health_version_api import LOCAL_TURNS_EXECUTION_MODE
from packages.telemetry import InMemoryTraceReader


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_FOUNDATION_MODEL = "fake-model"
STARTUP_MESSAGE_PREFIX = "Core service startup metadata: "

ServerFactory = Callable[[str, int, Any], Any]


@dataclass(frozen=True)
class CoreServiceEntrypointConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    local_auth_token: str | None = None
    foundation_model: str = DEFAULT_FOUNDATION_MODEL

    def local_api_config(self) -> LocalApiConfig:
        return LocalApiConfig(host=self.host, port=self.port)


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
) -> CoreService:
    effective_trace_reader = trace_reader or InMemoryTraceReader()
    executor = (
        _create_foundation_turn_executor(trace_reader=effective_trace_reader)
        if enable_foundation_turns
        else _HealthOnlyTurnExecutor()
    )
    return CoreService(turn_executor=executor)


def create_core_service_app(
    *,
    config: CoreServiceEntrypointConfig,
    trace_reader: InMemoryTraceReader | None = None,
) -> tuple[Any, CoreService]:
    service = create_core_service(trace_reader=trace_reader)
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Core service local entrypoint. Defaults to loopback 127.0.0.1; "
            "remote bind modes are not supported."
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
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Loopback bind host. Defaults to 127.0.0.1.",
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.health_once:
        return run_health_once()
    try:
        return run_core_service(
            config=CoreServiceEntrypointConfig(
                host=args.host,
                port=args.port,
                local_auth_token=args.local_auth_token,
            )
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
