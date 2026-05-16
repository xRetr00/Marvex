import json

import pytest


class RecordingRequester:
    def __init__(self):
        self.calls = []

    def __call__(self, *, method, url, headers, body):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": body,
            }
        )
        return 200, {"ok": True}


def safe_discovery_payload(**overrides):
    payload = {
        "schema_version": "0.1.1-draft",
        "service": "marvex-local-api",
        "base_url": "http://127.0.0.1:8765",
        "bind_host": "127.0.0.1",
        "port": 8765,
        "auth_required": True,
        "auth_token_present": True,
        "token_value_logged": False,
        "discovery_mode": "future_local_file",
        "discovery_file_path": None,
        "process_id": 123,
        "started_at": "2026-05-16T00:00:00Z",
        "contract_versions": {"LocalApiStartup": "0.1.1-draft"},
        "warnings": [],
    }
    payload.update(overrides)
    return payload


def test_client_loads_safe_discovery_metadata_without_token_storage(tmp_path):
    from packages.local_api_client import load_local_api_client_from_discovery

    discovery_file = tmp_path / "marvex" / "local-api.json"
    discovery_file.parent.mkdir(parents=True)
    discovery_file.write_text(
        json.dumps(safe_discovery_payload()),
        encoding="utf-8",
    )

    client = load_local_api_client_from_discovery(
        discovery_file_path=str(discovery_file),
        local_user_root=tmp_path,
        requester=RecordingRequester(),
    )

    assert client.base_url == "http://127.0.0.1:8765"
    assert client.auth_required is True
    assert client.auth_token_present is True
    assert "local_auth_token" not in repr(client)
    assert "Bearer" not in repr(client)


def test_public_readiness_requests_do_not_send_auth_header():
    from packages.local_api_client import LocalApiClient

    requester = RecordingRequester()
    client = LocalApiClient.from_discovery_metadata(
        safe_discovery_payload(),
        requester=requester,
    )

    response = client.get_health()

    assert response.status_code == 200
    assert response.body == {"ok": True}
    assert requester.calls == [
        {
            "method": "GET",
            "url": "http://127.0.0.1:8765/health",
            "headers": {"Accept": "application/json"},
            "body": None,
        }
    ]


def test_turn_request_requires_explicit_token_and_sends_bearer_auth():
    from packages.local_api_client import LocalApiClient

    requester = RecordingRequester()
    client = LocalApiClient.from_discovery_metadata(
        safe_discovery_payload(),
        requester=requester,
    )
    body = {"schema_version": "0.1.1-draft"}

    with pytest.raises(ValueError, match="local_auth_token is required"):
        client.post_turn(body)

    response = client.post_turn(body, local_auth_token="fake-local-token")

    assert response.status_code == 200
    assert requester.calls == [
        {
            "method": "POST",
            "url": "http://127.0.0.1:8765/v1/turns",
            "headers": {
                "Accept": "application/json",
                "Authorization": "Bearer fake-local-token",
                "Content-Type": "application/json",
            },
            "body": json.dumps(body, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            ),
        }
    ]


def test_trace_request_requires_explicit_token_and_validates_trace_id():
    from packages.local_api_client import LocalApiClient

    requester = RecordingRequester()
    client = LocalApiClient.from_discovery_metadata(
        safe_discovery_payload(),
        requester=requester,
    )

    with pytest.raises(ValueError, match="local_auth_token is required"):
        client.get_trace("trace-client-test")
    with pytest.raises(ValueError, match="trace_id must be non-empty"):
        client.get_trace(" ", local_auth_token="fake-local-token")

    response = client.get_trace(
        "trace-client-test",
        local_auth_token="fake-local-token",
    )

    assert response.status_code == 200
    assert requester.calls == [
        {
            "method": "GET",
            "url": "http://127.0.0.1:8765/v1/traces/trace-client-test",
            "headers": {
                "Accept": "application/json",
                "Authorization": "Bearer fake-local-token",
            },
            "body": None,
        }
    ]


def test_client_rejects_remote_or_token_bearing_discovery_metadata():
    from packages.local_api_client import LocalApiClient

    with pytest.raises(ValueError, match="loopback"):
        LocalApiClient.from_discovery_metadata(
            safe_discovery_payload(
                base_url="http://0.0.0.0:8765",
                bind_host="0.0.0.0",
            ),
            requester=RecordingRequester(),
        )

    with pytest.raises(ValueError, match="unsafe"):
        LocalApiClient.from_discovery_metadata(
            safe_discovery_payload(local_auth_token="fake-token-must-not-load"),
            requester=RecordingRequester(),
        )
