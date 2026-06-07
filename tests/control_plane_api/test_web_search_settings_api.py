from __future__ import annotations

from packages.control_plane_api import ControlPlaneSnapshot
from packages.web_search_runtime.config import WebSearchSettingsStore
from tests.control_plane_api.asgi_helpers import asgi_call, create_control_plane_test_app


def test_web_search_settings_can_be_read_and_updated(tmp_path) -> None:
    store = WebSearchSettingsStore(path=tmp_path / "web_search.json")
    app = create_control_plane_test_app(
        approval_store=None,
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        web_search_settings=store,
    )

    status, _headers, initial = asgi_call(app, "/control/web-search")
    update_status, _update_headers, updated = asgi_call(
        app,
        "/control/web-search",
        method="POST",
        body={"searxng_base_url": "http://127.0.0.1:7777"},
    )

    assert status == "200 OK"
    assert initial["provider_order"] == ["searxng", "ddgs"]
    assert update_status == "200 OK"
    assert updated["searxng_base_url"] == "http://127.0.0.1:7777"
    assert store.load().searxng_base_url == "http://127.0.0.1:7777"
