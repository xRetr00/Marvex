from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from services.desktop_agent.controller import DesktopAgentController
from services.desktop_agent.models import DesktopAgentCommandResult


def run_health_once() -> int:
    print(DesktopAgentController().health().model_dump_json())
    return 0


def run_version_once() -> int:
    print(DesktopAgentController().version().model_dump_json())
    return 0


def run_jsonl() -> int:
    controller = DesktopAgentController()
    for line in sys.stdin:
        if not line.strip():
            continue
        result = handle_jsonl_command(controller, line)
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True), flush=True)
        if result.command == "stop" and result.ok:
            break
    return 0


def handle_jsonl_command(controller: DesktopAgentController, line: str) -> DesktopAgentCommandResult:
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
            return DesktopAgentCommandResult(
                command="health",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"health": controller.health().model_dump(mode="json")},
            )
        if command == "version":
            return DesktopAgentCommandResult(
                command="version",
                ok=True,
                trace_id=trace_id,
                state=controller.status(trace_id=trace_id).state,
                metadata={"version": controller.version().model_dump(mode="json")},
            )
        if command == "perceive":
            return controller.perceive(
                trace_id=trace_id,
                content_budget_chars=_optional_int(payload.get("content_budget_chars")),
            )
        if command == "recall":
            return controller.recall(
                trace_id=trace_id,
                query=_optional_string(payload.get("query")) or "screenpipe recall",
                limit=_optional_int(payload.get("limit")) or 5,
            )
        return controller.validation_result(trace_id=trace_id, reason="unsupported_command")
    except Exception:
        trace_id = "trace-desktop-agent-validation"
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                trace_id = _trace_id(payload)
        except Exception:
            pass
        return controller.validation_result(trace_id=trace_id, reason="invalid_command")


def _trace_id(payload: dict[str, Any]) -> str:
    value = payload.get("trace_id")
    return value if isinstance(value, str) and value.strip() else "trace-desktop-agent"


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DesktopAgent local JSONL process entrypoint.")
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
