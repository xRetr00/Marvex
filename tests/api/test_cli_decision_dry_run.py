import pytest


def test_decision_dry_run_command_is_not_a_cli_surface(capsys):
    from apps.cli.main import main

    with pytest.raises(SystemExit) as error:
        main(["decision-dry-run", "hello"])

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
