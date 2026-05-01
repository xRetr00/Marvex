import json
from pathlib import Path

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


def test_normal_cli_without_preflight_remains_unchanged(capsys):
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


def test_cli_preflight_uses_turn_preflight_boundary_before_provider(monkeypatch, capsys):
    from apps.cli import main as cli_main

    calls: list[str] = []

    def fake_turn_preflight(input_text: str, enabled: bool) -> dict[str, object]:
        calls.append(f"preflight:{enabled}")
        return {
            "enabled": enabled,
            "observed": True,
            "final_action": "clarify",
            "reason_code": "validator.dev_clarify",
            "blocking_applied": False,
            "decision_pipeline_result": {
                "prompt_plan": {"tool_surface_exposed": []},
            },
        }

    monkeypatch.setattr(cli_main, "run_dev_turn_preflight", fake_turn_preflight)
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
    assert calls == ["preflight:True", "provider"]
    assert preflight["turn_preflight"]["final_action"] == "clarify"
    assert preflight["turn_preflight"]["blocking_applied"] is False
    assert lines[1] == "recorded output"


def test_cli_preflight_deny_still_does_not_block_provider(monkeypatch, capsys):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "run_dev_turn_preflight",
        lambda input_text, enabled: {
            "enabled": enabled,
            "observed": True,
            "final_action": "deny",
            "reason_code": "policy.denied",
            "blocking_applied": False,
            "decision_pipeline_result": {
                "prompt_plan": {"tool_surface_exposed": []},
            },
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
    assert preflight["turn_preflight"]["final_action"] == "deny"
    assert preflight["turn_preflight"]["blocking_applied"] is False
    assert lines[1] == "fake provider response"


def test_cli_preflight_output_has_no_prompt_tools_mcp_memory_or_provider_payload(capsys):
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

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    encoded = json.dumps(payload).lower()
    assert exit_code == 0
    assert payload["turn_preflight"]["decision_pipeline_result"]["prompt_plan"]["tool_surface_exposed"] == []
    assert "rendered_prompt" not in encoded
    assert "tool_catalog" not in encoded
    assert "mcp" not in encoded
    assert "memory" not in encoded
    assert "provider_payload" not in encoded


def test_cli_turn_preflight_no_longer_calls_raw_decision_pipeline_helper() -> None:
    source = (Path("apps") / "cli" / "main.py").read_text(encoding="utf-8")

    assert "run_dev_turn_preflight" in source
    assert "_print_decision_preflight(args.text)" not in source
