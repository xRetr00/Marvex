from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

from packages.contracts import (
    AssistantInputSource,
    AssistantMode,
    AssistantTurnInput,
    AssistantTurnResult,
    InputEvent,
    InputModality,
    PolicyContext,
    Privacy,
    Sensitivity,
    Source,
    TextPayload,
    TurnInput,
)
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig
from packages.runtime_composition import (
    run_fake_provider_assistant_bridge,
    run_provider_foundation_turn,
)


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
    if args.assistant_runtime_fake_provider:
        return _run_assistant_runtime_fake_provider_foundation(args)
    return _run_turn(args, parser)


def _run_turn(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    turn_input = TurnInput(
        schema_version=SCHEMA_VERSION,
        trace_id=f"trace-{uuid4()}",
        turn_id=f"turn-{uuid4()}",
        input_text=args.text,
        previous_response_id=args.previous_response_id,
        source=Source.CLI,
        metadata={},
    )
    try:
        output = run_provider_foundation_turn(
            turn_input,
            provider_name=args.provider,
            model=args.model,
            instructions=args.instructions,
        )
    except ValueError as exc:
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return 2

    print(output.final_response.text)
    if output.provider_response_id is not None:
        print(f"provider_response_id: {output.provider_response_id}")
    print(f"trace_id: {output.trace_id}")
    return 0


def _run_assistant_runtime_fake_provider_foundation(args: argparse.Namespace) -> int:
    turn_input = _build_assistant_runtime_turn_input(args)
    telemetry_sink = (
        _build_assistant_runtime_cli_telemetry_sink()
        if args.assistant_runtime_provider_stage_trace
        else None
    )
    result = run_fake_provider_assistant_bridge(
        turn_input,
        model=args.model,
        instructions=args.instructions,
        previous_response_id=args.previous_response_id,
        telemetry_sink=telemetry_sink,
    )
    _print_assistant_runtime_provider_stage_result(result)
    return 0 if result.error is None else 1


def _build_assistant_runtime_cli_telemetry_sink() -> object | None:
    return None


def _build_assistant_runtime_turn_input(
    args: argparse.Namespace,
) -> AssistantTurnInput:
    trace_id = f"trace-{uuid4()}"
    event_id = f"event-{uuid4()}"
    input_event = InputEvent(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        event_id=event_id,
        source=AssistantInputSource.CLI,
        input_modality=InputModality.TEXT,
        payload=TextPayload(kind="text", text=args.text),
        payload_ref=None,
        session_ref=None,
        privacy=Privacy(
            sensitivity=Sensitivity.NORMAL,
            redaction_needed=False,
        ),
        timestamp=datetime.now(UTC),
        metadata={},
    )
    return AssistantTurnInput(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        turn_id=f"turn-{uuid4()}",
        input_event_id=input_event.event_id,
        session_ref=input_event.session_ref,
        identity_ref=None,
        user_visible_input=input_event.payload.text if input_event.payload else None,
        assistant_mode=AssistantMode.DEFAULT,
        policy_context=PolicyContext(
            requested_capabilities=[],
            sensitivity=input_event.privacy.sensitivity,
        ),
        metadata={},
    )


def _print_assistant_runtime_provider_stage_result(
    result: AssistantTurnResult,
) -> None:
    if result.assistant_final_response is not None:
        print(result.assistant_final_response.text)
    elif result.error is not None:
        print(result.error.message)
        print(f"error_code: {result.error.code.value}")
    if result.provider_turn_refs:
        print(f"provider_response_id: {result.provider_turn_refs[0].ref_id}")
    print(f"trace_id: {result.trace_id}")
    print(f"turn_id: {result.turn_id}")


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
    required = [("--text", "text"), ("--model", "model")]
    if not args.assistant_runtime_fake_provider:
        required.append(("--provider", "provider"))
    for option, name in required:
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
    parser.add_argument(
        "--assistant-runtime-fake-provider",
        "--assistant-runtime-provider-stage-fake",
        action="store_true",
        dest="assistant_runtime_fake_provider",
    )
    parser.add_argument("--assistant-runtime-provider-stage-trace", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
