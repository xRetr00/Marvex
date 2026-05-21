from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from .controller import ToolWorkerController
from .models import ToolWorkerCommandResult


def run_health_once() -> int:
    print(ToolWorkerController().health().model_dump_json())
    return 0


def run_version_once() -> int:
    print(ToolWorkerController().version().model_dump_json())
    return 0


def run_jsonl() -> int:
    controller = ToolWorkerController()
    for line in sys.stdin:
        if not line.strip():
            continue
        result = handle_jsonl_command(controller, line)
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True), flush=True)
        if result.command == "stop" and result.ok:
            break
    return 0


def handle_jsonl_command(
    controller: ToolWorkerController,
    line: str,
) -> ToolWorkerCommandResult:
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
            return ToolWorkerCommandResult(
                command="health",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"health": controller.health().model_dump(mode="json")},
            )
        if command == "version":
            return ToolWorkerCommandResult(
                command="version",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"version": controller.version().model_dump(mode="json")},
            )
        if command in {"execute", "run_capability"}:
            return controller.execute(
                trace_id=trace_id,
                turn_id=_required_string(payload.get("turn_id")),
                capability_id=_required_string(payload.get("capability_id")),
                action=_required_string(payload.get("action")),
                capability=_required_string(payload.get("capability")),
                resource_type=_required_string(payload.get("resource_type")),
                arguments=_arguments(payload),
            )
        return controller.validation_result(trace_id=trace_id, reason="unsupported_command")
    except Exception:
        trace_id = "trace-tool-worker-validation"
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                trace_id = _trace_id(payload)
        except Exception:
            pass
        return controller.validation_result(trace_id=trace_id, reason="invalid_command")


def _trace_id(payload: dict[str, Any]) -> str:
    value = payload.get("trace_id")
    return value if isinstance(value, str) and value.strip() else "trace-tool-worker"


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("required string missing")
    return value


def _arguments(payload: dict[str, Any]) -> dict[str, object]:
    value = payload.get("arguments")
    return dict(value) if isinstance(value, dict) else {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ToolWorker local JSONL process entrypoint.")
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
