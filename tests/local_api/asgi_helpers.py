from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient


def asgi_call(
    app,
    path: str,
    *,
    method: str = "GET",
    body: object = None,
    auth: str | None = None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    headers: dict[str, str] = {}
    if auth is not None:
        headers["Authorization"] = auth
    if isinstance(body, bytes):
        response = TestClient(app).request(
            method,
            path,
            headers=headers,
            content=body,
            follow_redirects=False,
        )
    else:
        response = TestClient(app).request(
            method,
            path,
            headers=headers,
            json=body,
            follow_redirects=False,
        )
    status = f"{response.status_code} {response.reason_phrase}"
    headers_out = dict(response.headers)
    headers_out.update({key.title(): value for key, value in response.headers.items()})
    return status, headers_out, json.loads(response.text)
