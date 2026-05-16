from pathlib import Path

import pytest


def test_startup_generates_non_constant_local_bearer_tokens():
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup

    first = create_local_api_startup(LocalApiServiceStartupConfig())
    second = create_local_api_startup(LocalApiServiceStartupConfig())

    assert first.local_auth_token
    assert second.local_auth_token
    assert first.local_auth_token != second.local_auth_token


def test_public_metadata_excludes_raw_token_and_reports_presence_only():
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup

    result = create_local_api_startup(
        LocalApiServiceStartupConfig(local_auth_token="fake-token-for-test")
    )

    public = result.public_metadata()
    public_dump = public.to_dict()
    public_text = repr(public_dump)

    assert public.auth_token_present is True
    assert public.token_value_logged is False
    assert "fake-token-for-test" not in public_text
    assert "MARVEX_LMSTUDIO_API_KEY" not in public_text
    assert "api_key" not in public_text


def test_public_metadata_contains_safe_startup_fields_only():
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup

    result = create_local_api_startup(
        LocalApiServiceStartupConfig(
            discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
            discovery_file_path="future/local/file.json",
        )
    )

    public = result.public_metadata()

    assert public.schema_version == "0.1.1-draft"
    assert public.service == "marvex-local-api"
    assert public.base_url == "http://127.0.0.1:8765"
    assert public.bind_host == "127.0.0.1"
    assert public.port == 8765
    assert public.auth_required is True
    assert public.auth_token_present is True
    assert public.discovery_mode == DiscoveryMode.FUTURE_LOCAL_FILE
    assert public.discovery_file_path == "future/local/file.json"
    assert isinstance(public.process_id, int)
    assert public.process_id > 0
    assert public.started_at.endswith("Z")
    assert public.contract_versions == {"LocalApiStartup": "0.1.1-draft"}
    assert public.warnings == ("discovery_file_write_blocked",)


def test_default_bind_host_is_loopback_and_remote_bind_is_rejected():
    from packages.local_service_startup import LocalApiServiceStartupConfig

    assert LocalApiServiceStartupConfig().bind_host == "127.0.0.1"

    with pytest.raises(ValueError, match="bind_host must be 127.0.0.1"):
        LocalApiServiceStartupConfig(bind_host="0.0.0.0")

    with pytest.raises(ValueError, match="bind_host must be 127.0.0.1"):
        LocalApiServiceStartupConfig(bind_host="192.168.1.10")


def test_discovery_file_writing_is_not_performed(tmp_path):
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup

    discovery_file = tmp_path / "marvex-local-api.json"

    result = create_local_api_startup(
        LocalApiServiceStartupConfig(
            discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
            discovery_file_path=str(discovery_file),
        )
    )

    assert result.public_metadata().discovery_file_path == str(discovery_file)
    assert not discovery_file.exists()


def test_startup_result_separates_raw_secret_from_safe_metadata():
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup

    result = create_local_api_startup(
        LocalApiServiceStartupConfig(local_auth_token="fake-token-for-test")
    )

    assert result.local_auth_token == "fake-token-for-test"
    assert "fake-token-for-test" not in result.public_metadata().to_json()


def test_shutdown_semantics_are_explicit_without_daemon_supervision():
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup import create_local_api_startup

    semantics = create_local_api_startup(
        LocalApiServiceStartupConfig()
    ).shutdown_semantics

    assert semantics.startup_explicit is True
    assert semantics.shutdown_explicit is True
    assert semantics.daemon_loop_started is False
    assert semantics.auto_restart_enabled is False
    assert semantics.supervisor_started is False


def test_core_provider_runtime_and_local_api_do_not_import_startup_package():
    forbidden = "packages.local_service_startup"
    roots = [
        Path("packages/core"),
        Path("packages/provider_runtime"),
        Path("packages/local_api"),
    ]

    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            if forbidden in path.read_text(encoding="utf-8"):
                offenders.append(path.as_posix())

    assert offenders == []

