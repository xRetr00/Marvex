import json
from types import SimpleNamespace

from packages.contracts import HealthCheck, ProviderRequest, VersionInfo


def test_fake_provider_path_returns_deterministic_response(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "fake provider response" in output
    assert "provider_response_id: fake-response-001" in output
    assert "trace_id: " in output


def test_previous_response_id_reaches_orchestrator_path(monkeypatch, capsys):
    from apps.cli import main as cli_main

    seen_requests: list[ProviderRequest] = []

    class RecordingProvider:
        def send(self, request: ProviderRequest):
            seen_requests.append(request)
            from packages.contracts import FinishReason, ProviderResponse

            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="recording",
                response_id="recorded-response",
                output_text="recorded output",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
            )

    monkeypatch.setattr(
        cli_main,
        "create_provider",
        lambda config: RecordingProvider(),
    )

    exit_code = cli_main.main(
        [
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
            "--previous-response-id",
            "prev-123",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert seen_requests[0].previous_response_id == "prev-123"
    assert "recorded output" in output


def test_output_includes_response_text_provider_response_id_and_trace_id(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 0
    assert lines[0] == "fake provider response"
    assert lines[1] == "provider_response_id: fake-response-001"
    assert lines[2].startswith("trace_id: ")


def test_unknown_provider_exits_non_zero(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--text",
            "Hello",
            "--provider",
            "unknown",
            "--model",
            "fake-model",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "unsupported provider" in captured.err


def test_litellm_path_uses_mocked_litellm_call(monkeypatch, capsys):
    from apps.cli.main import main
    from packages.adapters.providers.litellm import litellm_provider

    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            id="litellm-response-001",
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="litellm output"),
                )
            ],
            usage={},
        )

    monkeypatch.setattr(litellm_provider.litellm, "completion", fake_completion)

    exit_code = main(
        [
            "--text",
            "Hello",
            "--provider",
            "litellm",
            "--model",
            "openrouter/test-model",
            "--instructions",
            "Be concise.",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "litellm output" in output
    assert calls == [
        {
            "model": "openrouter/test-model",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ],
        }
    ]


def test_health_command_prints_human_health_output(capsys):
    from apps.cli.main import main

    exit_code = main(["health"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "service: marvex" in output
    assert "status: ok" in output
    assert "version: 0.1.0" in output
    assert "uptime_seconds: 0.0" in output


def test_health_command_json_output_validates_as_health_check(capsys):
    from apps.cli.main import main

    exit_code = main(["health", "--json"])

    output = capsys.readouterr().out
    health = HealthCheck.model_validate(json.loads(output))
    assert exit_code == 0
    assert health.service == "marvex"
    assert health.status == "ok"
    assert health.version == "0.1.0"
    assert health.uptime_seconds == 0.0
    assert health.dependencies == {}


def test_version_command_prints_human_version_output(capsys):
    from apps.cli.main import main

    exit_code = main(["version"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "service: marvex" in output
    assert "service_version: 0.1.0" in output


def test_version_command_json_output_validates_as_version_info(capsys):
    from apps.cli.main import main

    exit_code = main(["version", "--json"])

    output = capsys.readouterr().out
    version = VersionInfo.model_validate(json.loads(output))
    assert exit_code == 0
    assert version.service == "marvex"
    assert version.service_version == "0.1.0"
    assert version.contract_versions == {
        "HealthCheck": "0.1.1-draft",
        "VersionInfo": "0.1.1-draft",
    }
    assert version.build == {"version": "0.1.0"}


def test_cli_source_has_no_forbidden_modules_or_features():
    from pathlib import Path

    source = (Path("apps") / "cli" / "main.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "packages.ports",
        "packages.telemetry",
        "lmstudio",
        "http.server",
        "fastapi",
        "flask",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "tool",
        "mcp",
        "stream",
        "memory",
        "intent",
        "voice",
        "desktop",
        "session",
        "history",
        "retry",
        "fallback",
        "packages.adapters",
        "fakeprovider",
        "litellmprovider",
        "http",
        "os.environ",
        "getenv",
        "open(",
        "service runtime",
        "provider health",
        "provider probe",
    ]

    assert [token for token in forbidden if token in source] == []


def test_cli_uses_provider_runtime_for_provider_selection():
    from pathlib import Path

    source = (Path("apps") / "cli" / "main.py").read_text(encoding="utf-8")

    assert "from packages.provider_runtime import ProviderRuntimeConfig, create_provider" in source
    assert "create_provider(ProviderRuntimeConfig(provider_name=args.provider))" in source
    assert "_create_provider_for_cli_bootstrap" not in source


def test_cli_imports_public_turn_orchestrator_only():
    from pathlib import Path

    source = (Path("apps") / "cli" / "main.py").read_text(encoding="utf-8")

    assert "from packages.core.orchestration import TurnOrchestrator" in source
    assert "packages.core.orchestration.turn_orchestrator" not in source


def test_process_runtime_boundary_allows_only_cli_main_integration():
    from pathlib import Path

    source = (Path("scripts") / "check_process_runtime_boundaries.py").read_text(
        encoding="utf-8"
    )

    assert 'CLI_PROCESS_RUNTIME_ALLOWED = {"apps/cli/main.py"}' in source
    assert "for root in [CORE_ROOT, CLI_ROOT, PROVIDER_RUNTIME_ROOT]" in source
    assert "if root == CLI_ROOT and rel in CLI_PROCESS_RUNTIME_ALLOWED:" in source
    assert "PROVIDER_RUNTIME_ROOT" in source
