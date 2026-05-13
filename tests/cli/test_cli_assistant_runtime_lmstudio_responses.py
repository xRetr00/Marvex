from pathlib import Path

from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantResponseType,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    OutputChannelIntent,
    ProviderTurnRef,
    StageStatus,
    StageSummary,
)


def make_assistant_result(
    *,
    text: str | None = "LM Studio assistant response.",
    trace_id: str = "trace-lmstudio-cli",
    turn_id: str = "turn-lmstudio-cli",
    response_id: str = "lmstudio-response-cli",
    error_code: ErrorCode | None = None,
    error_message: str | None = None,
) -> AssistantTurnResult:
    failed = error_code is not None
    return AssistantTurnResult(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id=turn_id,
        assistant_final_response=None
        if failed
        else AssistantFinalResponse(
            schema_version="0.1.1-draft",
            response_type=AssistantResponseType.TEXT,
            text=text or "",
            payload_ref=None,
            output_channel_intent=OutputChannelIntent.DEFAULT,
            safe_for_display=True,
            safe_for_speech=True,
            memory_write_candidate_hint=False,
            finish_reason=AssistantFinishReason.STOP,
            metadata={},
        ),
        output_events=[],
        stage_summaries=[
            StageSummary(
                stage_name="provider_stage",
                status=StageStatus.FAILED if failed else StageStatus.COMPLETED,
                started_at=None,
                completed_at=None,
                ref=None,
                error_ref="lmstudio-cli-error" if failed else None,
            )
        ],
        provider_turn_refs=[
            ProviderTurnRef(
                ref_type="provider_turn",
                ref_id=response_id,
                stage_name="provider_stage",
                provider_name="lmstudio_responses",
                status=StageStatus.FAILED if failed else StageStatus.COMPLETED,
                trace_id=trace_id,
            )
        ],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None
        if not failed
        else ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id=trace_id,
            error_id="lmstudio-cli-error",
            code=error_code,
            message=error_message or "Provider stage failed.",
            recoverable=False,
            source="provider",
            details={},
        ),
        metadata={},
    )


def test_lmstudio_responses_mode_calls_runtime_composition_bridge(
    monkeypatch, capsys
):
    from apps.cli import main as cli_main

    captured = {}

    def fake_run_lmstudio_responses_assistant_bridge(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return make_assistant_result()

    monkeypatch.setattr(
        cli_main,
        "run_lmstudio_responses_assistant_bridge",
        fake_run_lmstudio_responses_assistant_bridge,
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-lmstudio-responses",
            "--text",
            "Hello",
            "--model",
            "local-model",
            "--instructions",
            "Be concise.",
            "--previous-response-id",
            "previous-lmstudio-response",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 0
    assert captured["args"][0].user_visible_input == "Hello"
    assert captured["kwargs"]["model"] == "local-model"
    assert captured["kwargs"]["instructions"] == "Be concise."
    assert captured["kwargs"]["previous_response_id"] == "previous-lmstudio-response"
    assert captured["kwargs"]["telemetry_sink"] is None
    assert lines == [
        "LM Studio assistant response.",
        "provider_response_id: lmstudio-response-cli",
        "trace_id: trace-lmstudio-cli",
        "turn_id: turn-lmstudio-cli",
    ]


def test_lmstudio_responses_mode_does_not_require_provider_argument(
    monkeypatch, capsys
):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "run_lmstudio_responses_assistant_bridge",
        lambda *args, **kwargs: make_assistant_result(),
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-lmstudio-responses",
            "--text",
            "Hello",
            "--model",
            "local-model",
        ]
    )

    assert exit_code == 0
    assert "LM Studio assistant response." in capsys.readouterr().out


def test_default_and_fake_cli_modes_remain_unchanged(capsys):
    from apps.cli.main import main

    default_exit = main(["--text", "Hello", "--provider", "fake", "--model", "fake"])
    default_lines = capsys.readouterr().out.strip().splitlines()
    fake_exit = main(["--assistant-runtime-fake-provider", "--text", "Hello", "--model", "fake"])
    fake_lines = capsys.readouterr().out.strip().splitlines()
    alias_exit = main(
        ["--assistant-runtime-provider-stage-fake", "--text", "Hello", "--model", "fake"]
    )
    alias_lines = capsys.readouterr().out.strip().splitlines()

    assert default_exit == 0
    assert default_lines[0] == "fake provider response"
    assert len(default_lines) == 3
    assert fake_exit == 0
    assert fake_lines[0] == "fake provider response"
    assert len(fake_lines) == 4
    assert alias_exit == 0
    assert alias_lines[0] == "fake provider response"
    assert len(alias_lines) == 4


def test_lmstudio_responses_provider_error_prints_safe_output(monkeypatch, capsys):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "run_lmstudio_responses_assistant_bridge",
        lambda *args, **kwargs: make_assistant_result(
            text=None,
            response_id="lmstudio-error-response",
            error_code=ErrorCode.PROVIDER_ERROR,
            error_message="Provider returned a safe error.",
        ),
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-lmstudio-responses",
            "--text",
            "Hello",
            "--model",
            "local-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 1
    assert lines[:3] == [
        "Provider returned a safe error.",
        "error_code: PROVIDER_ERROR",
        "provider_response_id: lmstudio-error-response",
    ]
    assert lines[3] == "trace_id: trace-lmstudio-cli"
    assert lines[4] == "turn_id: turn-lmstudio-cli"


def test_lmstudio_responses_unavailable_and_timeout_errors_are_safe(
    monkeypatch, capsys
):
    from apps.cli import main as cli_main

    scenarios = [
        (ErrorCode.PROVIDER_UNAVAILABLE, "Provider unavailable."),
        (ErrorCode.PROVIDER_TIMEOUT, "Provider request timed out."),
    ]
    for code, message in scenarios:
        monkeypatch.setattr(
            cli_main,
            "run_lmstudio_responses_assistant_bridge",
            lambda *args, _code=code, _message=message, **kwargs: make_assistant_result(
                text=None,
                response_id=f"{_code.value.lower()}-response",
                error_code=_code,
                error_message=_message,
            ),
        )

        exit_code = cli_main.main(
            [
                "--assistant-runtime-lmstudio-responses",
                "--text",
                "Hello",
                "--model",
                "local-model",
            ]
        )

        lines = capsys.readouterr().out.strip().splitlines()
        assert exit_code == 1
        assert lines == [
            message,
            f"error_code: {code.value}",
            f"provider_response_id: {code.value.lower()}-response",
            "trace_id: trace-lmstudio-cli",
            "turn_id: turn-lmstudio-cli",
        ]


def test_lmstudio_responses_empty_output_prints_safe_output(monkeypatch, capsys):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "run_lmstudio_responses_assistant_bridge",
        lambda *args, **kwargs: make_assistant_result(
            text=None,
            response_id="lmstudio-empty-response",
            error_code=ErrorCode.VALIDATION_ERROR,
            error_message="Provider output was empty.",
        ),
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-lmstudio-responses",
            "--text",
            "Hello",
            "--model",
            "local-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 1
    assert lines[:3] == [
        "Provider output was empty.",
        "error_code: VALIDATION_ERROR",
        "provider_response_id: lmstudio-empty-response",
    ]
    assert lines[3] == "trace_id: trace-lmstudio-cli"
    assert lines[4] == "turn_id: turn-lmstudio-cli"


def test_lmstudio_responses_malformed_provider_response_prints_safe_output(
    monkeypatch, capsys
):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "run_lmstudio_responses_assistant_bridge",
        lambda *args, **kwargs: make_assistant_result(
            text=None,
            response_id="lmstudio-malformed-response",
            error_code=ErrorCode.VALIDATION_ERROR,
            error_message="Malformed provider response.",
        ),
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-lmstudio-responses",
            "--text",
            "Hello",
            "--model",
            "local-model",
        ]
    )

    assert exit_code == 1
    assert capsys.readouterr().out.strip().splitlines() == [
        "Malformed provider response.",
        "error_code: VALIDATION_ERROR",
        "provider_response_id: lmstudio-malformed-response",
        "trace_id: trace-lmstudio-cli",
        "turn_id: turn-lmstudio-cli",
    ]


def test_lmstudio_responses_manual_smoke_docs_define_failure_policy():
    smoke_docs = Path("docs/SMOKE_TESTING.md").read_text(encoding="utf-8")

    required_phrases = [
        "LM Studio local server must be running",
        "A model must be loaded",
        "Expected success output",
        "Expected failure output",
        "provider unavailable / connection refused",
        "model missing or rejected by backend",
        "timeout-like failure",
        "provider error response",
        "empty output",
        "malformed provider response",
        "not part of CI or `run_all_checks.py`",
    ]

    assert [phrase for phrase in required_phrases if phrase not in smoke_docs] == []


def test_cli_source_uses_only_runtime_composition_for_lmstudio_responses_mode():
    source = Path("apps/cli/main.py").read_text(encoding="utf-8")

    assert "run_lmstudio_responses_assistant_bridge" in source
    assert "packages.provider_runtime" not in source
    assert "packages.adapters" not in source
    assert "ProviderRuntimeConfig" not in source
    assert "create_provider" not in source
    assert "LMStudioResponsesProvider" not in source
