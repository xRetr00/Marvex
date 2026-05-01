from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

from packages.contracts import Source, TurnInput
from packages.core.orchestration import TurnOrchestrator
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig
from packages.provider_runtime import ProviderRuntimeConfig, create_provider


SCHEMA_VERSION = "0.1.1-draft"
SERVICE_NAME = "marvex"
SERVICE_VERSION = "0.1.0"
LOCAL_RUNTIME_STARTED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        return _run_health(json_output=args.json_output)
    if args.command == "version":
        return _run_version(json_output=args.json_output)

    _require_turn_args(parser, args)
    return _run_turn(args, parser)


def _run_turn(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        provider = create_provider(ProviderRuntimeConfig(provider_name=args.provider))
    except ValueError as exc:
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return 2

    turn_input = TurnInput(
        schema_version=SCHEMA_VERSION,
        trace_id=f"trace-{uuid4()}",
        turn_id=f"turn-{uuid4()}",
        input_text=args.text,
        previous_response_id=args.previous_response_id,
        source=Source.CLI,
        metadata={},
    )
    output = TurnOrchestrator(
        provider,
        model=args.model,
        instructions=args.instructions,
    ).run_turn(turn_input)

    print(output.final_response.text)
    if output.provider_response_id is not None:
        print(f"provider_response_id: {output.provider_response_id}")
    print(f"trace_id: {output.trace_id}")
    return 0


def _run_health(*, json_output: bool) -> int:
    health = _local_runtime_provider().get_health()

    if json_output:
        print(health.model_dump_json())
        return 0

    print(f"service: {health.service}")
    print(f"status: {health.status.value}")
    print(f"version: {health.version}")
    print(f"uptime_seconds: {health.uptime_seconds}")
    return 0


def _run_version(*, json_output: bool) -> int:
    version = _local_runtime_provider().get_version()

    if json_output:
        print(version.model_dump_json())
        return 0

    print(f"service: {version.service}")
    print(f"service_version: {version.service_version}")
    return 0


def _local_runtime_provider() -> HealthVersionProvider:
    return HealthVersionProvider(
        ProcessRuntimeConfig(
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            started_at=LOCAL_RUNTIME_STARTED_AT,
            clock=lambda: LOCAL_RUNTIME_STARTED_AT,
            contract_versions={
                "HealthCheck": SCHEMA_VERSION,
                "VersionInfo": SCHEMA_VERSION,
            },
            build={"version": SERVICE_VERSION},
            dependencies={},
        )
    )


def _require_turn_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    missing = []
    for option, name in [
        ("--text", "text"),
        ("--provider", "provider"),
        ("--model", "model"),
    ]:
        if getattr(args, name) is None:
            missing.append(option)
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marvex")
    subparsers = parser.add_subparsers(dest="command")

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--json", action="store_true", dest="json_output")

    version_parser = subparsers.add_parser("version")
    version_parser.add_argument("--json", action="store_true", dest="json_output")

    parser.add_argument("--text")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--instructions")
    parser.add_argument("--previous-response-id")
    return parser


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
