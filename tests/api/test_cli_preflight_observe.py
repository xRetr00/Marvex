import pytest


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


def test_decision_preflight_flag_is_not_supported_by_cli(capsys):
    from apps.cli.main import main

    with pytest.raises(SystemExit) as error:
        main(
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

    assert error.value.code == 2
    assert "unrecognized arguments: --decision-preflight" in capsys.readouterr().err
