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


def test_service_runner_rejects_future_discovery_file_write_mode():
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
                discovery_file_path="future/local/file.json",
            ),
            api_runner=api_runner,
        )
    except ValueError as exc:
        assert str(exc) == "discovery file writes are not approved for this runner"
    else:
        raise AssertionError("future discovery file mode must be rejected")

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
