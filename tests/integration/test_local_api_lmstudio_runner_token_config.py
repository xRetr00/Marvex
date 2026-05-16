import json

from packages.contracts import AssistantTurnResult, TraceLevel, TraceStage
from packages.telemetry import make_trace_event
from tests.integration.test_local_api_lmstudio_turn_handler import (
    EXPECTED_TOKEN,
    RecordingServer,
    call_app,
    make_payload,
    success_result,
)


def test_lmstudio_runner_injects_handler_trace_reader_and_fake_api_key(monkeypatch):
    import packages.runtime_composition.local_api_lmstudio_responses_runner as runner

    captured: dict[str, object] = {}
    server = RecordingServer()

    def fake_handler_factory(*, telemetry_sink=None, lmstudio_responses_api_key=None):
        captured["telemetry_sink"] = telemetry_sink
        captured["lmstudio_responses_api_key"] = lmstudio_responses_api_key

        def handle(request):
            telemetry_sink.emit(
                make_trace_event(
                    schema_version=request.assistant_turn_input.schema_version,
                    trace_id=request.assistant_turn_input.trace_id,
                    turn_id=request.assistant_turn_input.turn_id,
                    stage=TraceStage.TURN_COMPLETED,
                    level=TraceLevel.INFO,
                    message="Manual smoke LM Studio turn completed.",
                    data={
                        "status": "success",
                        "provider_response_id": "must-not-appear",
                    },
                )
            )
            return success_result(request.assistant_turn_input)

        return handle

    def server_factory(host, port, app):
        captured["host"] = host
        captured["port"] = port
        captured["app"] = app
        return server

    monkeypatch.setattr(
        runner,
        "create_local_api_lmstudio_turn_handler",
        fake_handler_factory,
    )

    exit_code = runner.run_local_lmstudio_responses_api(
        dev_token=EXPECTED_TOKEN,
        lmstudio_responses_api_key="fake-lmstudio-token-for-test",
        server_factory=server_factory,
    )

    turn_status, turn_payload = call_app(captured["app"], body=make_payload())
    trace_status, trace_payload = call_app(
        captured["app"],
        "/v1/traces/trace-local-api-lmstudio",
        method="GET",
    )
    serialized_trace = json.dumps(trace_payload)

    assert exit_code == 0
    assert server.served is True
    assert server.closed is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
    assert captured["telemetry_sink"] is not None
    assert captured["lmstudio_responses_api_key"] == "fake-lmstudio-token-for-test"
    assert turn_status == "200 OK"
    assert AssistantTurnResult.model_validate(turn_payload).trace_id == (
        "trace-local-api-lmstudio"
    )
    assert trace_status == "200 OK"
    assert trace_payload["scope"] == "current_process"
    assert trace_payload["source"] == "in_memory"
    assert trace_payload["event_count"] >= 1
    assert "data" not in trace_payload["events"][0]
    assert "provider_response_id" not in serialized_trace
    assert "must-not-appear" not in serialized_trace
    assert "fake-lmstudio-token-for-test" not in serialized_trace


def test_lmstudio_runner_uses_none_when_provider_token_env_var_is_missing(
    monkeypatch,
):
    import packages.runtime_composition.local_api_lmstudio_responses_runner as runner

    monkeypatch.delenv("MARVEX_LMSTUDIO_API_KEY", raising=False)

    assert runner.read_lmstudio_responses_api_key_from_env() is None


def test_lmstudio_runner_reads_provider_token_env_var_without_printing_value(
    monkeypatch,
    capsys,
):
    import packages.runtime_composition.local_api_lmstudio_responses_runner as runner

    fake_api_key = "fake-lmstudio-token-for-test"
    monkeypatch.setenv("MARVEX_LMSTUDIO_API_KEY", fake_api_key)

    assert runner.read_lmstudio_responses_api_key_from_env() == fake_api_key
    captured = capsys.readouterr()
    assert fake_api_key not in captured.out
    assert fake_api_key not in captured.err


def test_lmstudio_runner_rejects_blank_dev_token_before_starting():
    from packages.runtime_composition.local_api_lmstudio_responses_runner import (
        run_local_lmstudio_responses_api,
    )

    def server_factory(_host, _port, _app):
        raise AssertionError("server must not start without a dev token")

    try:
        run_local_lmstudio_responses_api(
            dev_token=" ",
            server_factory=server_factory,
        )
    except ValueError as exc:
        assert str(exc) == "dev_token must be a non-empty fake/dev-only token"
    else:
        raise AssertionError("blank dev token must be rejected")
