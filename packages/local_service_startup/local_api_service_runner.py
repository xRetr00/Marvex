from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from packages.local_api.contracts import LocalApiConfig
from packages.local_api.runner import run_local_health_version_api

from .discovery import write_local_api_discovery_metadata
from .startup import DiscoveryMode, LocalApiServiceStartupConfig
from .startup import create_local_api_startup


ApiRunner = Callable[..., int]


def run_local_api_service_with_startup(
    *,
    startup_config: LocalApiServiceStartupConfig | None = None,
    api_runner: ApiRunner = run_local_health_version_api,
    discovery_local_user_root: str | Path | None = None,
) -> int:
    config = startup_config or LocalApiServiceStartupConfig()
    if (
        config.discovery_mode == DiscoveryMode.FUTURE_LOCAL_FILE
        and not config.discovery_file_path
    ):
        raise ValueError("discovery_file_path is required for discovery writes")

    startup = create_local_api_startup(config)
    metadata = startup.public_metadata()
    if config.discovery_mode == DiscoveryMode.FUTURE_LOCAL_FILE:
        write_local_api_discovery_metadata(
            metadata,
            discovery_file_path=config.discovery_file_path or "",
            local_user_root=discovery_local_user_root,
        )
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
    parser.add_argument(
        "--discovery-file",
        default=None,
        help=(
            "Write safe local-user-scoped discovery metadata to this explicit "
            "path. The file never contains the raw bearer token."
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    api_runner: ApiRunner = run_local_health_version_api,
    discovery_local_user_root: str | Path | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    discovery_mode = (
        DiscoveryMode.FUTURE_LOCAL_FILE
        if args.discovery_file
        else DiscoveryMode.DISABLED
    )
    try:
        return run_local_api_service_with_startup(
            startup_config=LocalApiServiceStartupConfig(
                port=args.port,
                discovery_mode=discovery_mode,
                discovery_file_path=args.discovery_file,
            ),
            api_runner=api_runner,
            discovery_local_user_root=discovery_local_user_root,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
