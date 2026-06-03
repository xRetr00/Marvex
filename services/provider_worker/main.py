from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import Any

from packages.contracts import ErrorCode, ErrorEnvelope, ProviderRequest

from services.provider_worker.controller import ProviderWorkerController
from services.provider_worker.models import SCHEMA_VERSION, ProviderWorkerCommandResult


def run_health_once() -> int:
    print(ProviderWorkerController().health().model_dump_json())
    return 0


def run_version_once() -> int:
    print(ProviderWorkerController().version().model_dump_json())
    return 0


def run_jsonl() -> int:
    controller = ProviderWorkerController()
    for line in sys.stdin:
        if not line.strip():
            continue
        if _is_stream_command(line):
            for frame in handle_stream_command(controller, line):
                print(json.dumps(frame, sort_keys=True), flush=True)
            continue
        result = handle_jsonl_command(controller, line)
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True), flush=True)
        if result.command == "stop" and result.ok:
            break
    return 0


def _is_stream_command(line: str) -> bool:
    try:
        payload = json.loads(line)
    except Exception:
        return False
    return isinstance(payload, dict) and payload.get("command") == "stream"


def handle_stream_command(controller: ProviderWorkerController, line: str):
    """Yield JSONL frames for a streaming turn, each echoing trace_id+command.

    The frames produced by the controller ({type:delta|final|error}) are wrapped
    with the request's trace_id so the core IPC client can match them and the
    multi-frame reader can route them to the in-flight stream request.
    """

    try:
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("command must be a JSON object")
        trace_id = _trace_id(payload)
        request = ProviderRequest.model_validate(payload.get("request"))
        frames = controller.stream(
            provider_name=_provider_name(payload),
            request=request,
            base_url=_optional_string(payload.get("base_url")),
            provider_mode=_optional_string(payload.get("provider_mode")),
            timeout_seconds=_optional_float(payload.get("timeout_seconds")),
            lmstudio_responses_api_key=_optional_string(payload.get("lmstudio_responses_api_key")),
            litellm_api_key=_optional_string(payload.get("litellm_api_key")),
        )
        for frame in frames:
            yield {"command": "stream", "trace_id": trace_id, **frame}
    except Exception:
        yield {
            "command": "stream",
            "trace_id": "trace-provider-worker-validation",
            "type": "error",
            "message": "ProviderWorker stream command failed.",
        }


def handle_jsonl_command(
    controller: ProviderWorkerController,
    line: str,
) -> ProviderWorkerCommandResult:
    try:
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("command must be a JSON object")
        command = payload.get("command")
        trace_id = _trace_id(payload)
        if command == "start":
            return controller.start(trace_id=trace_id)
        if command == "stop":
            return controller.stop(trace_id=trace_id)
        if command == "status":
            return controller.status(trace_id=trace_id)
        if command == "health":
            return ProviderWorkerCommandResult(
                command="health",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"health": controller.health().model_dump(mode="json")},
            )
        if command == "version":
            return ProviderWorkerCommandResult(
                command="version",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"version": controller.version().model_dump(mode="json")},
            )
        if command == "send":
            request = ProviderRequest.model_validate(payload.get("request"))
            return controller.send(
                provider_name=_provider_name(payload),
                request=request,
                base_url=_optional_string(payload.get("base_url")),
                provider_mode=_optional_string(payload.get("provider_mode")),
                timeout_seconds=_optional_float(payload.get("timeout_seconds")),
                lmstudio_responses_api_key=_optional_string(
                    payload.get("lmstudio_responses_api_key")
                ),
                litellm_api_key=_optional_string(payload.get("litellm_api_key")),
            )
        if command == "structured_output":
            return controller.map_structured_output(
                provider_name=_provider_name(payload),
                schema_version=_optional_string(payload.get("schema_version")) or SCHEMA_VERSION,
                trace_id=trace_id,
                turn_id=_optional_string(payload.get("turn_id")) or "turn-provider-worker",
                target_contract=_optional_string(payload.get("target_contract")) or "",
                raw_output_text=_optional_string(payload.get("raw_output_text")) or "",
                base_url=_optional_string(payload.get("base_url")),
                provider_mode=_optional_string(payload.get("provider_mode")),
                timeout_seconds=_optional_float(payload.get("timeout_seconds")),
                lmstudio_responses_api_key=_optional_string(
                    payload.get("lmstudio_responses_api_key")
                ),
                litellm_api_key=_optional_string(payload.get("litellm_api_key")),
            )
        return _validation_result(trace_id=trace_id, reason="unsupported_command")
    except Exception:
        return _validation_result(trace_id="trace-provider-worker-validation", reason="invalid_command")


def _trace_id(payload: dict[str, Any]) -> str:
    value = payload.get("trace_id")
    return value if isinstance(value, str) and value.strip() else "trace-provider-worker"


def _provider_name(payload: dict[str, Any]) -> str:
    value = payload.get("provider_name")
    if isinstance(value, str) and value.strip():
        return value
    return _optional_string(os.environ.get("MARVEX_WORKER_PROVIDER")) or "lmstudio_responses"


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _validation_result(*, trace_id: str, reason: str) -> ProviderWorkerCommandResult:
    return ProviderWorkerCommandResult(
        command="status",
        ok=False,
        trace_id=trace_id,
        error=ErrorEnvelope(
            schema_version=SCHEMA_VERSION,
            trace_id=trace_id,
            error_id=f"{trace_id}:provider-worker:{reason}",
            code=ErrorCode.VALIDATION_ERROR,
            message="ProviderWorker command validation failed.",
            recoverable=False,
            source="provider_worker",
            details={"reason": reason},
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ProviderWorker local JSONL process entrypoint."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--health-once", action="store_true")
    mode.add_argument("--version-once", action="store_true")
    mode.add_argument("--jsonl", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.health_once:
        return run_health_once()
    if args.version_once:
        return run_version_once()
    if args.jsonl:
        return run_jsonl()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
