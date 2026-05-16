import json

import pytest


def test_discovery_writer_writes_safe_loopback_metadata_without_raw_token(tmp_path):
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup
    from packages.local_service_startup.discovery import (
        write_local_api_discovery_metadata,
    )

    discovery_file = tmp_path / "marvex" / "local-api.json"
    startup = create_local_api_startup(
        LocalApiServiceStartupConfig(
            discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
            discovery_file_path=str(discovery_file),
            local_auth_token="fake-token-must-not-be-written",
        )
    )

    result = write_local_api_discovery_metadata(
        startup.public_metadata(),
        discovery_file_path=str(discovery_file),
        local_user_root=tmp_path,
    )

    payload = json.loads(discovery_file.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)
    assert result.discovery_file_path == str(discovery_file.resolve())
    assert result.token_value_written is False
    assert payload["base_url"] == "http://127.0.0.1:8765"
    assert payload["bind_host"] == "127.0.0.1"
    assert payload["auth_required"] is True
    assert payload["auth_token_present"] is True
    assert payload["token_value_logged"] is False
    assert "fake-token-must-not-be-written" not in serialized
    assert "local_auth_token" not in serialized
    assert "api_key" not in serialized


def test_discovery_writer_rejects_paths_outside_local_user_scope(tmp_path):
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup
    from packages.local_service_startup.discovery import (
        write_local_api_discovery_metadata,
    )

    startup = create_local_api_startup(LocalApiServiceStartupConfig())
    outside_path = tmp_path.parent / "outside-local-user-scope.json"

    with pytest.raises(ValueError, match="local-user scoped"):
        write_local_api_discovery_metadata(
            startup.public_metadata(),
            discovery_file_path=str(outside_path),
            local_user_root=tmp_path,
        )

    assert not outside_path.exists()


def test_discovery_writer_rejects_remote_bind_metadata(tmp_path):
    from packages.local_service_startup import LocalApiStartupMetadata
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup.discovery import (
        write_local_api_discovery_metadata,
    )

    metadata = LocalApiStartupMetadata(
        schema_version="0.1.1-draft",
        service="marvex-local-api",
        base_url="http://0.0.0.0:8765",
        bind_host="0.0.0.0",
        port=8765,
        auth_required=True,
        auth_token_present=True,
        token_value_logged=False,
        discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
        discovery_file_path=str(tmp_path / "local-api.json"),
        process_id=123,
        started_at="2026-05-16T00:00:00Z",
        contract_versions={"LocalApiStartup": "0.1.1-draft"},
    )

    with pytest.raises(ValueError, match="loopback"):
        write_local_api_discovery_metadata(
            metadata,
            discovery_file_path=str(tmp_path / "local-api.json"),
            local_user_root=tmp_path,
        )

    assert not (tmp_path / "local-api.json").exists()
