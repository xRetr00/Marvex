from pathlib import Path

import pytest


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


def test_cli_rejects_decision_preflight_flag(capsys):
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


def test_cli_source_has_no_decision_runtime_dependency() -> None:
    source = (Path("apps") / "cli" / "main.py").read_text(encoding="utf-8")

    assert "packages.decision_runtime" not in source
    assert "run_dev" not in source
    assert "decision_preflight" not in source
