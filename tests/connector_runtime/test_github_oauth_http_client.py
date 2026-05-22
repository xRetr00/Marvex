from __future__ import annotations

from typing import Any

from packages.adapters.connectors.github_connector import (
    GITHUB_CONNECTOR_REF,
    GitHubConnectorAdapter,
    make_oauth_token_http_get,
)


class _FakeResponse:
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return (
            b'[{"id":"n-1","subject":{"type":"Issue","title":"Runtime connector item"},'
            b'"reason":"assigned"}]'
        )


def test_github_oauth_http_get_injects_token_without_returning_it() -> None:
    captured: dict[str, Any] = {}

    def _fake_urlopen(req: Any, timeout: float) -> _FakeResponse:
        captured["url"] = req.full_url
        captured["authorization"] = req.get_header("Authorization")
        captured["timeout"] = timeout
        return _FakeResponse()

    http_get = make_oauth_token_http_get(
        access_token="gho_test_token",
        timeout_seconds=3.0,
        urlopen=_fake_urlopen,
    )
    adapter = GitHubConnectorAdapter(http_get=http_get)

    page = adapter.fetch_page(GITHUB_CONNECTOR_REF, cursor=None)

    assert captured["authorization"] == "Bearer gho_test_token"
    assert captured["timeout"] == 3.0
    assert page.items[0][1] == "Runtime connector item"
    serialized = page.model_dump_json().lower()
    assert "gho_test_token" not in serialized
    assert page.raw_payload_persisted is False
