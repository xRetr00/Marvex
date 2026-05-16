from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from packages.local_api.health_version_api import LocalApiConfig
from packages.local_api.runner import run_local_health_version_api

from .startup import DiscoveryMode, LocalApiServiceStartupConfig
from .startup import create_local_api_startup


ApiRunner = Callable[..., int]


def run_local_api_service_with_startup(
    *,
    startup_config: LocalApiServiceStartupConfig | None = None,
    api_runner: ApiRunner = run_local_health_version_api,
) -> int:
    config = startup_config or LocalApiServiceStartupConfig()
    if config.discovery_mode == DiscoveryMode.FUTURE_LOCAL_FILE:
        raise ValueError("discovery file writes are not approved for this runner")

    startup = create_local_api_startup(config)
    metadata = startup.public_metadata()
    return api_runner(
        config=LocalApiConfig(host=metadata.bind_host, port=metadata.port),
        local_auth_token=startup.local_auth_token,
        startup_message=(
            "Local API service startup metadata: "
            f"{metadata.to_json()}"
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    defaults = LocalApiServiceStartupConfig()
    parser = argparse.ArgumentParser(
        description="Local API service startup proof with generated bearer auth."
    )
    parser.add_argument(
        "--port",
        default=defaults.port,
        type=int,
        help="Bind port for the local API service startup proof. Defaults to 8765.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run_local_api_service_with_startup(
            startup_config=LocalApiServiceStartupConfig(port=args.port)
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
