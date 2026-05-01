import json
from types import SimpleNamespace

from packages.contracts import FinishReason, ProviderRequest, ProviderResponse


class RecordingProvider:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.calls.append("provider")
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


def test_normal_cli_turn_path_is_unchanged_without_preflight(capsys):
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


def test_decision_preflight_runs_before_provider_and_provider_still_runs(monkeypatch, capsys):
    from apps.cli import main as cli_main

    calls: list[str] = []

    def fake_preflight(input_text: str) -> dict[str, object]:
        calls.append("preflight")
        return {
            "final_action": "proceed",
            "reason_code": "pipeline.proceed",
            "prompt_plan": {"tool_surface_exposed": []},
        }

    monkeypatch.setattr(cli_main, "run_dev_decision_pipeline", fake_preflight)
    monkeypatch.setattr(
        cli_main,
        "create_provider",
        lambda config: RecordingProvider(calls),
    )

    exit_code = cli_main.main(
        [
            "--decision-preflight",
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    preflight = json.loads(lines[0])
    assert exit_code == 0
    assert calls == ["preflight", "provider"]
    assert preflight["decision_preflight"]["final_action"] == "proceed"
    assert lines[1] == "recorded output"


def test_clarify_preflight_does_not_block_provider(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--decision-preflight",
            "--text",
            "",
            "--provider",
            "fake",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    preflight = json.loads(lines[0])
    assert exit_code == 0
    assert preflight["decision_preflight"]["final_action"] == "clarify"
    assert lines[1] == "fake provider response"


def test_deny_preflight_summary_does_not_block_provider(monkeypatch, capsys):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "run_dev_decision_pipeline",
        lambda input_text: {
            "final_action": "deny",
            "reason_code": "policy.denied",
            "prompt_plan": {"tool_surface_exposed": []},
        },
    )

    exit_code = cli_main.main(
        [
            "--decision-preflight",
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    preflight = json.loads(lines[0])
    assert exit_code == 0
    assert preflight["decision_preflight"]["final_action"] == "deny"
    assert lines[1] == "fake provider response"


def test_preflight_output_is_summarized_without_prompt_or_runtime_payloads(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--decision-preflight",
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
        ]
    )

    first_line = capsys.readouterr().out.strip().splitlines()[0]
    payload = json.loads(first_line)
    encoded = json.dumps(payload).lower()
    assert exit_code == 0
    assert payload["decision_preflight"]["prompt_plan"]["tool_surface_exposed"] == []
    assert "rendered_prompt" not in encoded
    assert "tool_catalog" not in encoded
    assert "mcp" not in encoded
    assert "memory" not in encoded
    assert "provider_payload" not in encoded
