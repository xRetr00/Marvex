from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from packages.control_plane_api import ControlPlaneRuntime
from packages.control_plane_api.asgi_app import create_control_plane_asgi_app


def create_control_plane_test_app(**kwargs: Any):
    web_dist = kwargs.pop("web_dist", None)
    runtime = ControlPlaneRuntime(**kwargs)
    return create_control_plane_asgi_app(runtime=runtime, web_dist=web_dist)


def asgi_call(
    app,
    path: str,
    *,
    method: str = "GET",
    token: str | None = "fake-control-token",
    cookie: str | None = None,
    body: dict[str, Any] | None = None,
):
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if cookie is not None:
        headers["Cookie"] = cookie
    response = TestClient(app).request(
        method,
        path,
        headers=headers,
        json=body or {},
        follow_redirects=False,
    )
    status = f"{response.status_code} {response.reason_phrase}"
    headers = dict(response.headers)
    headers.update({key.title(): value for key, value in response.headers.items()})
    return status, headers, response.json()
