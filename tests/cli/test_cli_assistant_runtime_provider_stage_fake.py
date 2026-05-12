from pathlib import Path

import pytest

from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantResponseType,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    OutputChannelIntent,
    ProviderRequest,
    ProviderResponse,
    ProviderTurnRef,
    StageStatus,
    StageSummary,
    TraceEvent,
    TraceStage,
)


class RecordingProvider:
    def __init__(self, response: ProviderResponse | None = None) -> None:
        self.requests: list[ProviderRequest] = []
        self.response = response

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if self.response is not None:
            return self.response
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="cli_dev_provider",
            response_id="cli-dev-response-001",
            output_text="CLI dev provider response.",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def make_assistant_result() -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version="0.1.1-draft",
        trace_id="trace-sentinel",
        turn_id="turn-sentinel",
        assistant_final_response=AssistantFinalResponse(
            schema_version="0.1.1-draft",
            response_type=AssistantResponseType.TEXT,
            text="sentinel assistant response",
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
                status=StageStatus.COMPLETED,
                started_at=None,
                completed_at=None,
                ref=None,
                error_ref=None,
            )
        ],
        provider_turn_refs=[
            ProviderTurnRef(
                ref_type="provider_turn",
                ref_id="sentinel-provider-response",
                stage_name="provider_stage",
                provider_name="cli_dev_provider",
                status=StageStatus.COMPLETED,
                trace_id="trace-sentinel",
            )
        ],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )


def provider_error_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-error",
        turn_id="turn-error",
        provider_name="cli_dev_provider",
        response_id="cli-dev-error-response",
        output_text="",
        finish_reason=FinishReason.ERROR,
        usage={},
        raw_metadata={},
        error=ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-error",
            error_id="cli-dev-error",
            code=ErrorCode.PROVIDER_ERROR,
            message="CLI dev provider safe error.",
            recoverable=False,
            source="provider",
            details={},
        ),
    )


def empty_provider_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-empty",
        turn_id="turn-empty",
        provider_name="cli_dev_provider",
        response_id="cli-dev-empty-response",
        output_text="",
        finish_reason=FinishReason.STOP,
        usage={},
        raw_metadata={},
        error=None,
    )


def test_default_cli_behavior_remains_unchanged(capsys):
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
    assert len(lines) == 3


def test_opt_in_cli_path_calls_core_helper(monkeypatch, capsys):
    from apps.cli import main as cli_main

    captured = {}

    def fake_run_assistant_provider_stage_turn(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return make_assistant_result()

    monkeypatch.setattr(
        cli_main,
        "run_assistant_provider_stage_turn",
        fake_run_assistant_provider_stage_turn,
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--text",
            "Hello",
            "--model",
            "fake-model",
            "--instructions",
            "Be concise.",
            "--previous-response-id",
            "previous-cli-response",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    turn_input = captured["args"][0]
    assert exit_code == 0
    assert turn_input.user_visible_input == "Hello"
    assert captured["kwargs"]["model"] == "fake-model"
    assert captured["kwargs"]["instructions"] == "Be concise."
    assert captured["kwargs"]["previous_response_id"] == "previous-cli-response"
    assert captured["kwargs"]["telemetry_sink"] is None
    assert hasattr(captured["kwargs"]["provider"], "send")
    assert lines == [
        "sentinel assistant response",
        "provider_response_id: sentinel-provider-response",
        "trace_id: trace-sentinel",
        "turn_id: turn-sentinel",
    ]


def test_opt_in_success_preserves_ids_and_provider_ref(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--text",
            "Hello",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 0
    assert lines[0] == "assistant runtime fake provider response"
    assert lines[1] == "provider_response_id: assistant-runtime-fake-response-001"
    assert lines[2].startswith("trace_id: trace-")
    assert lines[3].startswith("turn_id: turn-")


def test_opt_in_previous_response_id_reaches_injected_provider(monkeypatch, capsys):
    from apps.cli import main as cli_main

    provider = RecordingProvider()
    monkeypatch.setattr(
        cli_main,
        "_build_assistant_runtime_provider_stage_dev_provider",
        lambda: provider,
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--text",
            "Hello",
            "--model",
            "fake-model",
            "--previous-response-id",
            "previous-cli-response",
        ]
    )

    assert exit_code == 0
    assert provider.requests[0].schema_version == "0.1.1-draft"
    assert provider.requests[0].input_text == "Hello"
    assert provider.requests[0].previous_response_id == "previous-cli-response"
    capsys.readouterr()


def test_opt_in_fake_provider_error_maps_to_safe_cli_output(monkeypatch, capsys):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "_build_assistant_runtime_provider_stage_dev_provider",
        lambda: RecordingProvider(provider_error_response()),
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--text",
            "Hello",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 1
    assert lines[:3] == [
        "CLI dev provider safe error.",
        "error_code: PROVIDER_ERROR",
        "provider_response_id: cli-dev-error-response",
    ]
    assert lines[3].startswith("trace_id: trace-")
    assert lines[4].startswith("turn_id: turn-")


def test_opt_in_empty_fake_provider_output_maps_to_safe_cli_output(monkeypatch, capsys):
    from apps.cli import main as cli_main

    monkeypatch.setattr(
        cli_main,
        "_build_assistant_runtime_provider_stage_dev_provider",
        lambda: RecordingProvider(empty_provider_response()),
    )

    exit_code = cli_main.main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--text",
            "Hello",
            "--model",
            "fake-model",
        ]
    )

    lines = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 1
    assert lines[:3] == [
        "Provider output was empty.",
        "error_code: VALIDATION_ERROR",
        "provider_response_id: cli-dev-empty-response",
    ]
    assert lines[3].startswith("trace_id: trace-")
    assert lines[4].startswith("turn_id: turn-")


def test_opt_in_trace_diagnostics_use_telemetry_owned_event_construction(monkeypatch):
    from apps.cli import main as cli_main

    sink = RecordingTelemetrySink()
    monkeypatch.setattr(cli_main, "_build_assistant_runtime_cli_telemetry_sink", lambda: sink)

    exit_code = cli_main.main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--assistant-runtime-provider-stage-trace",
            "--text",
            "Hello",
            "--model",
            "fake-model",
        ]
    )

    assert exit_code == 0
    assert [event.stage for event in sink.events] == [
        TraceStage.PROVIDER_REQUEST_CREATED,
        TraceStage.PROVIDER_REQUEST_SENT,
        TraceStage.PROVIDER_RESPONSE_RECEIVED,
        TraceStage.FINAL_RESPONSE_CREATED,
        TraceStage.TURN_COMPLETED,
    ]
    assert all(event.trace_id.startswith("trace-") for event in sink.events)
    assert sink.events[0].data == {"stage": "provider_stage"}


def test_opt_in_cli_path_does_not_require_provider_argument(capsys):
    from apps.cli.main import main

    exit_code = main(
        [
            "--assistant-runtime-provider-stage-fake",
            "--text",
            "Hello",
            "--model",
            "fake-model",
        ]
    )

    assert exit_code == 0
    assert "assistant runtime fake provider response" in capsys.readouterr().out


def test_opt_in_cli_path_still_requires_text_and_model():
    from apps.cli.main import main

    with pytest.raises(SystemExit) as exc:
        main(["--assistant-runtime-provider-stage-fake", "--text", "Hello"])

    assert exc.value.code == 2


def test_cli_source_has_no_concrete_provider_adapter_imports_for_opt_in_path():
    source = Path("apps/cli/main.py").read_text(encoding="utf-8")

    assert "packages.adapters" not in source
    assert "FakeProvider" not in source
    assert "ProviderRuntime(" not in source
    assert "run_assistant_provider_stage_turn" in source
