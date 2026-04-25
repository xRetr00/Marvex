from __future__ import annotations

import argparse
import sys
from uuid import uuid4

from packages.contracts import Source, TurnInput
from packages.core.orchestration import TurnOrchestrator
from packages.provider_runtime import ProviderRuntimeConfig, create_provider


SCHEMA_VERSION = "0.1.1-draft"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marvex")
    parser.add_argument("--text", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--instructions")
    parser.add_argument("--previous-response-id")
    return parser

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
