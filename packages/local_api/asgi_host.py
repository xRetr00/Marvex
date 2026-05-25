from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import uvicorn
from fastapi import FastAPI

from .contracts import is_loopback_host


STARTUP_MESSAGE_PREFIX = "Core service startup metadata: "


class RunnableServer(Protocol):
    should_exit: bool

    def run(self) -> None:
        ...


ServerFactory = Callable[..., RunnableServer]


@dataclass(frozen=True)
class AsgiHostConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    control_host: str = "127.0.0.1"
    control_port: int = 8766
    allow_remote: bool = False

    def __post_init__(self) -> None:
        _validate_host("host", self.host, allow_remote=self.allow_remote)
        _validate_host("control_host", self.control_host, allow_remote=self.allow_remote)
        _validate_port("port", self.port)
        _validate_port("control_port", self.control_port)


def build_asgi_startup_message(
    *,
    config: AsgiHostConfig,
    service: str,
    provider: str,
) -> str:
    return STARTUP_MESSAGE_PREFIX + json.dumps(
        {
            "base_url": f"http://{config.host}:{config.port}",
            "control_base_url": f"http://{config.control_host}:{config.control_port}/control",
            "auth_required": True,
            "auth_token_present": True,
            "token_value_logged": False,
            "service": service,
            "provider": provider,
        },
        sort_keys=True,
    )


def run_dual_asgi_host(
    *,
    core_app: FastAPI,
    control_app: FastAPI,
    config: AsgiHostConfig,
    server_factory: ServerFactory | None = None,
    startup_message: str | None = None,
) -> int:
    factory = server_factory or _uvicorn_server
    control_server = factory(
        app=control_app,
        host=config.control_host,
        port=config.control_port,
        name="control",
    )
    core_server = factory(
        app=core_app,
        host=config.host,
        port=config.port,
        name="core",
    )

    if startup_message:
        print(startup_message)

    control_thread = threading.Thread(
        target=control_server.run,
        name="marvex-control-plane-asgi",
        daemon=True,
    )
    control_thread.start()
    try:
        core_server.run()
    except KeyboardInterrupt:
        pass
    finally:
        _request_shutdown(core_server)
        _request_shutdown(control_server)
        control_thread.join(timeout=2)
    return 0


def run_asgi_host(
    *,
    app: FastAPI,
    host: str,
    port: int,
    server_factory: ServerFactory | None = None,
    startup_message: str | None = None,
) -> int:
    _validate_host("host", host, allow_remote=False)
    _validate_port("port", port)
    server = (server_factory or _uvicorn_server)(
        app=app,
        host=host,
        port=port,
        name="local-api",
    )
    if startup_message:
        print(startup_message)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        _request_shutdown(server)
    return 0


def _uvicorn_server(*, app: FastAPI, host: str, port: int, name: str) -> uvicorn.Server:
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        server_header=False,
    )
    return uvicorn.Server(config)


def _request_shutdown(server: RunnableServer) -> None:
    try:
        server.should_exit = True
    except Exception:
        return


def _validate_host(name: str, host: str, *, allow_remote: bool) -> None:
    if not host or not host.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if not is_loopback_host(host) and not allow_remote:
        raise ValueError(f"{name} must be loopback-only")


def _validate_port(name: str, port: int) -> None:
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
