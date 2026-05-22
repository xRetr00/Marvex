from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from packages.contracts import ErrorCode, ErrorEnvelope

from services.intent_worker.controller import IntentWorkerController
from services.intent_worker.models import SCHEMA_VERSION, IntentWorkerCommandResult


def run_health_once() -> int:
    print(IntentWorkerController().health().model_dump_json())
    return 0


def run_version_once() -> int:
    print(IntentWorkerController().version().model_dump_json())
    return 0


def run_jsonl() -> int:
    controller = IntentWorkerController()
    for line in sys.stdin:
        if not line.strip():
            continue
        result = handle_jsonl_command(controller, line)
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True), flush=True)
        if result.command == "stop" and result.ok:
            break
    return 0


def handle_jsonl_command(
    controller: IntentWorkerController,
    line: str,
) -> IntentWorkerCommandResult:
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
            return IntentWorkerCommandResult(
                command="health",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"health": controller.health().model_dump(mode="json")},
            )
        if command == "version":
            return IntentWorkerCommandResult(
                command="version",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"version": controller.version().model_dump(mode="json")},
            )
        if command == "classify":
            return controller.classify(
                trace_id=trace_id,
                turn_id=_turn_id(payload),
                user_input_summary=_required_string(payload.get("user_input_summary")),
            )
        return _validation_result(trace_id=trace_id, reason="unsupported_command")
    except Exception:
        return _validation_result(trace_id="trace-intent-worker-validation", reason="invalid_command")


def _trace_id(payload: dict[str, Any]) -> str:
    value = payload.get("trace_id")
    return value if isinstance(value, str) and value.strip() else "trace-intent-worker"


def _turn_id(payload: dict[str, Any]) -> str:
    value = payload.get("turn_id")
    return value if isinstance(value, str) and value.strip() else "turn-intent-worker"


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("required string missing")
    return value


def _validation_result(*, trace_id: str, reason: str) -> IntentWorkerCommandResult:
    return IntentWorkerCommandResult(
        command="status",
        ok=False,
        trace_id=trace_id,
        error=ErrorEnvelope(
            schema_version=SCHEMA_VERSION,
            trace_id=trace_id,
            error_id=f"{trace_id}:intent-worker:{reason}",
            code=ErrorCode.VALIDATION_ERROR,
            message="IntentWorker command validation failed.",
            recoverable=False,
            source="intent_worker",
            details={"reason": reason},
        ),
        metadata={"raw_input_persisted": False},
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IntentWorker local JSONL process entrypoint.")
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
