from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import uvicorn
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI

from .health_version_api import WsgiApp, is_loopback_host


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


def create_asgi_app(wsgi_app: WsgiApp, *, title: str) -> FastAPI:
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/", WSGIMiddleware(wsgi_app))
    return app


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
    core_wsgi_app: WsgiApp,
    control_wsgi_app: WsgiApp,
    control_asgi_app: Any | None = None,
    config: AsgiHostConfig,
    server_factory: ServerFactory | None = None,
    startup_message: str | None = None,
) -> int:
    factory = server_factory or _uvicorn_server
    control_server = factory(
        app=control_asgi_app or create_asgi_app(control_wsgi_app, title="Marvex Control Plane"),
        host=config.control_host,
        port=config.control_port,
        name="control",
    )
    core_server = factory(
        app=create_asgi_app(core_wsgi_app, title="Marvex Core API"),
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
