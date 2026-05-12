from packages.contracts import FinalResponse, FinishReason, ResponseType, TurnOutput


def test_default_cli_calls_runtime_composition_provider_foundation_bridge(
    monkeypatch, capsys
):
    from apps.cli import main as cli_main

    captured = {}

    def fake_run_provider_foundation_turn(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        turn_input = args[0]
        return TurnOutput(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            final_response=FinalResponse(
                text="sentinel default response",
                response_type=ResponseType.TEXT,
                finish_reason=FinishReason.STOP,
                safe_for_tts=True,
                metadata={},
            ),
            provider_response_id="sentinel-default-provider-response",
            events=[],
            error=None,
        )

    monkeypatch.setattr(
        cli_main,
        "run_provider_foundation_turn",
        fake_run_provider_foundation_turn,
    )

    exit_code = cli_main.main(
        [
            "--text",
            "Hello",
            "--provider",
            "fake",
            "--model",
            "fake-model",
            "--instructions",
            "Be concise.",
            "--previous-response-id",
            "previous-default-response",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    turn_input = captured["args"][0]
    assert exit_code == 0
    assert turn_input.input_text == "Hello"
    assert turn_input.previous_response_id == "previous-default-response"
    assert captured["kwargs"] == {
        "provider_name": "fake",
        "model": "fake-model",
        "instructions": "Be concise.",
    }
    assert lines[0] == "sentinel default response"
    assert lines[1] == "provider_response_id: sentinel-default-provider-response"
