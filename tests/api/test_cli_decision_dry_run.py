import json


def test_decision_dry_run_command_returns_valid_json(capsys):
    from apps.cli.main import main

    exit_code = main(["decision-dry-run", "hello"])

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 0
    assert payload["final_action"] == "proceed"
    assert payload["reason_code"] == "pipeline.proceed"
    assert payload["intent_decision"]["route_family"] == "direct_answer"
    assert payload["intent_validation_result"]["accepted"] is True
    assert payload["policy_decision"]["allow"] is True
    assert "prompt_plan" in payload
    assert "prompt_assembly_report" in payload


def test_decision_dry_run_prompt_plan_summary_exposes_no_tool_surface(capsys):
    from apps.cli.main import main

    exit_code = main(["decision-dry-run", "hello"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["prompt_plan"]["tool_surface_exposed"] == []
    assert "blocks" not in payload["prompt_plan"]
    assert "block_count" in payload["prompt_plan"]


def test_decision_dry_run_output_contains_no_rendered_prompt_provider_tools_mcp_or_memory(capsys):
    from apps.cli.main import main

    exit_code = main(["decision-dry-run", "hello"])

    output = capsys.readouterr().out
    payload = json.loads(output)
    encoded = json.dumps(payload).lower()
    assert exit_code == 0
    assert "rendered_prompt" not in encoded
    assert "provider_payload" not in encoded
    assert "tool_catalog" not in encoded
    assert "mcp" not in encoded
    assert "memory" not in encoded


def test_decision_dry_run_does_not_call_provider_path(monkeypatch, capsys):
    from apps.cli import main as cli_main

    def fail_provider_call(config):
        raise AssertionError("provider path must not be called")

    monkeypatch.setattr(cli_main, "create_provider", fail_provider_call)

    exit_code = cli_main.main(["decision-dry-run", "hello"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["final_action"] == "proceed"


def test_decision_dry_run_empty_input_is_handled_safely(capsys):
    from apps.cli.main import main

    exit_code = main(["decision-dry-run", ""])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["final_action"] == "clarify"
    assert payload["intent_decision"]["route_family"] == "clarify"
    assert payload["intent_validation_result"]["needs_clarification"] is True
