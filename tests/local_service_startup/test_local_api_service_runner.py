import json


class RecordingApiRunner:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, **kwargs) -> int:
        self.calls.append(kwargs)
        return 0


def test_service_runner_injects_generated_token_into_local_api_runner_only():
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup.local_api_service_runner import (
        run_local_api_service_with_startup,
    )

    api_runner = RecordingApiRunner()

    exit_code = run_local_api_service_with_startup(
        startup_config=LocalApiServiceStartupConfig(
            local_auth_token="fake-startup-token-for-test"
        ),
        api_runner=api_runner,
    )

    assert exit_code == 0
    assert len(api_runner.calls) == 1
    call = api_runner.calls[0]
    assert call["local_auth_token"] == "fake-startup-token-for-test"
    assert call["config"].host == "127.0.0.1"
    assert call["config"].port == 8765
    assert "turn_handler" not in call
    assert "trace_reader" not in call


def test_service_runner_startup_message_contains_safe_metadata_not_raw_token():
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup.local_api_service_runner import (
        run_local_api_service_with_startup,
    )

    api_runner = RecordingApiRunner()

    run_local_api_service_with_startup(
        startup_config=LocalApiServiceStartupConfig(
            local_auth_token="fake-startup-token-for-test"
        ),
        api_runner=api_runner,
    )

    message = api_runner.calls[0]["startup_message"]
    assert "fake-startup-token-for-test" not in message
    assert "MARVEX_LMSTUDIO_API_KEY" not in message
    assert "api_key" not in message

    prefix = "Local API service startup metadata: "
    assert message.startswith(prefix)
    metadata = json.loads(message.removeprefix(prefix))
    assert metadata["base_url"] == "http://127.0.0.1:8765"
    assert metadata["auth_required"] is True
    assert metadata["auth_token_present"] is True
    assert metadata["token_value_logged"] is False
    assert metadata["discovery_mode"] == "disabled"


def test_service_runner_rejects_discovery_file_path_outside_local_user_scope(tmp_path):
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup.local_api_service_runner import (
        run_local_api_service_with_startup,
    )

    api_runner = RecordingApiRunner()
    outside_path = tmp_path.parent / "marvex-local-api.json"

    try:
        run_local_api_service_with_startup(
            startup_config=LocalApiServiceStartupConfig(
                discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
                discovery_file_path=str(outside_path),
                local_auth_token="fake-startup-token-for-test",
            ),
            api_runner=api_runner,
            discovery_local_user_root=tmp_path,
        )
    except ValueError as exc:
        assert str(exc) == "discovery_file_path must be local-user scoped"
    else:
        raise AssertionError("out-of-scope discovery file path must be rejected")

    assert api_runner.calls == []


def test_service_runner_allows_non_writing_explicit_config_discovery_mode():
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup.local_api_service_runner import (
        run_local_api_service_with_startup,
    )

    api_runner = RecordingApiRunner()

    exit_code = run_local_api_service_with_startup(
        startup_config=LocalApiServiceStartupConfig(
            discovery_mode=DiscoveryMode.EXPLICIT_CONFIG,
            local_auth_token="fake-startup-token-for-test",
        ),
        api_runner=api_runner,
    )

    metadata = json.loads(
        api_runner.calls[0]["startup_message"].removeprefix(
            "Local API service startup metadata: "
        )
    )
    assert exit_code == 0
    assert metadata["discovery_mode"] == "explicit_config"
    assert "fake-startup-token-for-test" not in api_runner.calls[0]["startup_message"]


def test_service_runner_writes_safe_discovery_file_when_explicitly_configured(tmp_path):
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup.local_api_service_runner import (
        run_local_api_service_with_startup,
    )

    api_runner = RecordingApiRunner()
    discovery_file = tmp_path / "marvex" / "local-api.json"

    exit_code = run_local_api_service_with_startup(
        startup_config=LocalApiServiceStartupConfig(
            discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
            discovery_file_path=str(discovery_file),
            local_auth_token="fake-startup-token-for-test",
        ),
        api_runner=api_runner,
        discovery_local_user_root=tmp_path,
    )

    payload = json.loads(discovery_file.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)
    assert exit_code == 0
    assert api_runner.calls[0]["local_auth_token"] == "fake-startup-token-for-test"
    assert payload["base_url"] == "http://127.0.0.1:8765"
    assert payload["auth_token_present"] is True
    assert payload["token_value_logged"] is False
    assert "fake-startup-token-for-test" not in serialized
    assert "local_auth_token" not in serialized


def test_service_runner_rejects_discovery_file_mode_without_path(tmp_path):
    from packages.local_service_startup import DiscoveryMode
    from packages.local_service_startup import LocalApiServiceStartupConfig
    from packages.local_service_startup.local_api_service_runner import (
        run_local_api_service_with_startup,
    )

    api_runner = RecordingApiRunner()

    try:
        run_local_api_service_with_startup(
            startup_config=LocalApiServiceStartupConfig(
                discovery_mode=DiscoveryMode.FUTURE_LOCAL_FILE,
                local_auth_token="fake-startup-token-for-test",
            ),
            api_runner=api_runner,
            discovery_local_user_root=tmp_path,
        )
    except ValueError as exc:
        assert str(exc) == "discovery_file_path is required for discovery writes"
    else:
        raise AssertionError("discovery file mode without a path must be rejected")

    assert api_runner.calls == []


def test_service_runner_cli_can_explicitly_write_safe_discovery_file(tmp_path):
    from packages.local_service_startup.local_api_service_runner import main

    api_runner = RecordingApiRunner()
    discovery_file = tmp_path / "marvex" / "local-api.json"

    exit_code = main(
        ["--port", "9876", "--discovery-file", str(discovery_file)],
        api_runner=api_runner,
        discovery_local_user_root=tmp_path,
    )

    payload = json.loads(discovery_file.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert api_runner.calls[0]["config"].port == 9876
    assert payload["base_url"] == "http://127.0.0.1:9876"
    assert payload["discovery_mode"] == "future_local_file"
    assert payload["token_value_logged"] is False
    assert "local_auth_token" not in json.dumps(payload, sort_keys=True)
