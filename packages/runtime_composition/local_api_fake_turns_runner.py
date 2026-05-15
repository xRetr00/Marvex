from __future__ import annotations

import argparse
from collections.abc import Sequence

from packages.local_api.health_version_api import LocalApiConfig
from packages.local_api.runner import ServerFactory, run_local_health_version_api
from packages.telemetry import InMemoryTraceReader

from .local_api_fake_turns import create_local_api_fake_turn_handler


def run_local_fake_turns_api(
    *,
    dev_token: str,
    config: LocalApiConfig = LocalApiConfig(),
    server_factory: ServerFactory | None = None,
) -> int:
    if not dev_token.strip():
        raise ValueError("dev_token must be a non-empty fake/dev-only token")

    startup_message = (
        "Local fake turns API smoke runner listening on "
        f"http://{config.host}:{config.port}; dev-only bearer token required."
    )
    trace_reader = InMemoryTraceReader()
    kwargs = {
        "config": config,
        "turn_handler": create_local_api_fake_turn_handler(telemetry_sink=trace_reader),
        "trace_reader": trace_reader,
        "local_auth_token": dev_token,
        "startup_message": startup_message,
    }
    if server_factory is not None:
        kwargs["server_factory"] = server_factory
    return run_local_health_version_api(**kwargs)


def _build_parser() -> argparse.ArgumentParser:
    defaults = LocalApiConfig()
    parser = argparse.ArgumentParser(
        description="Developer-only local API fake /v1/turns smoke runner."
    )
    parser.add_argument(
        "--dev-token",
        required=True,
        help="Fake/dev-only local bearer token for manual smoke. The value is not logged.",
    )
    parser.add_argument(
        "--port",
        default=defaults.port,
        type=int,
        help="Bind port for manual local smoke. Defaults to 8765.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run_local_fake_turns_api(
            dev_token=args.dev_token,
            config=LocalApiConfig(port=args.port),
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
