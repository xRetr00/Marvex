from __future__ import annotations

from pathlib import Path
import json
from dataclasses import dataclass
from typing import Any


def _wsgi_app(environ: dict[str, Any], start_response):
    path = str(environ.get("PATH_INFO", "/"))
    body = json.dumps({"path": path}).encode("utf-8")
    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]


@dataclass
class RecordingServer:
    name: str
    interrupt: bool = False
    ran: bool = False
    should_exit: bool = False

    def run(self) -> None:
        self.ran = True
        if self.interrupt:
            raise KeyboardInterrupt


def test_asgi_host_builds_fastapi_apps_from_wsgi_apps():
    from fastapi import FastAPI
    from packages.local_api.asgi_host import create_asgi_app

    app = create_asgi_app(_wsgi_app, title="Marvex Test")

    assert isinstance(app, FastAPI)
    assert app.title == "Marvex Test"
    assert app.routes


def test_asgi_host_builds_native_fallback_without_wsgi_middleware():
    from packages.local_api.asgi_host import create_asgi_app

    app = create_asgi_app(_wsgi_app, title="Marvex Test")
    mounted_apps = [getattr(route, "app", None) for route in app.routes]

    assert all(
        mounted_app is None or mounted_app.__class__.__name__ != "WSGIMiddleware"
        for mounted_app in mounted_apps
    )


def test_asgi_host_does_not_import_wsgi_middleware():
    source = Path("packages/local_api/asgi_host.py").read_text(encoding="utf-8")

    assert "starlette.middleware.wsgi" not in source
    assert "a2wsgi" not in source
    assert "WSGIMiddleware" not in source


def test_asgi_host_rejects_remote_hosts_by_default():
    from packages.local_api.asgi_host import AsgiHostConfig

    try:
        AsgiHostConfig(host="192.0.2.10")
    except ValueError as exc:
        assert str(exc) == "host must be loopback-only"
    else:
        raise AssertionError("remote core host must be rejected")

    try:
        AsgiHostConfig(control_host="192.0.2.20")
    except ValueError as exc:
        assert str(exc) == "control_host must be loopback-only"
    else:
        raise AssertionError("remote control host must be rejected")


def test_asgi_host_allows_remote_hosts_when_explicitly_opted_in():
    from packages.local_api.asgi_host import AsgiHostConfig

    config = AsgiHostConfig(
        host="192.0.2.10",
        control_host="192.0.2.20",
        allow_remote=True,
    )

    assert config.host == "192.0.2.10"
    assert config.control_host == "192.0.2.20"


def test_dual_asgi_host_runs_both_servers_and_shuts_down_on_interrupt():
    from packages.local_api.asgi_host import AsgiHostConfig, run_dual_asgi_host

    servers: list[RecordingServer] = []
    apps: dict[str, object] = {}

    def server_factory(*, app, host: str, port: int, name: str):
        server = RecordingServer(name=name, interrupt=name == "core")
        apps[name] = app
        servers.append(server)
        return server

    custom_control_app = object()
    exit_code = run_dual_asgi_host(
        core_wsgi_app=_wsgi_app,
        control_wsgi_app=_wsgi_app,
        control_asgi_app=custom_control_app,
        config=AsgiHostConfig(port=9875, control_port=9876),
        server_factory=server_factory,
        startup_message="safe startup",
    )

    assert exit_code == 0
    assert [server.name for server in servers] == ["control", "core"]
    assert apps["control"] is custom_control_app
    assert all(server.ran for server in servers)
    assert all(server.should_exit for server in servers)


def test_asgi_startup_message_is_compatible_and_does_not_include_raw_token():
    from packages.local_api.asgi_host import AsgiHostConfig, build_asgi_startup_message

    message = build_asgi_startup_message(
        config=AsgiHostConfig(port=9875, control_port=9876),
        service="marvex-core-service",
        provider="provider_worker",
    )

    prefix = "Core service startup metadata: "
    assert message.startswith(prefix)
    payload = json.loads(message.removeprefix(prefix))
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["base_url"] == "http://127.0.0.1:9875"
    assert payload["control_base_url"] == "http://127.0.0.1:9876/control"
    assert payload["auth_required"] is True
    assert payload["auth_token_present"] is True
    assert payload["token_value_logged"] is False
    assert payload["service"] == "marvex-core-service"
    assert payload["provider"] == "provider_worker"
    assert "fake-core-service-entrypoint-token" not in serialized
    assert "local_auth_token" not in serialized
