from __future__ import annotations

from types import SimpleNamespace

from scripts import spike_lmstudio_structured_output as spike


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(("parse", kwargs))
        return SimpleNamespace(
            status="completed",
            output_parsed=SimpleNamespace(
                schema_version="0.1.1-draft",
                response_type="text",
                text="ok",
            ),
            output_text='{"text":"ok"}',
        )

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(("create", kwargs))
        return SimpleNamespace(
            status="completed",
            incomplete_details=None,
            output_text='{"text":"raw fallback"}',
        )


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_parser_requires_model() -> None:
    parser = spike.build_parser()

    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("parser accepted missing --model")


def test_default_parser_values_are_manual_lmstudio_defaults() -> None:
    args = spike.build_parser().parse_args(["--model", "local-model"])

    assert args.base_url == "http://localhost:1234/v1"
    assert args.timeout_seconds == 30.0
    assert args.show_raw_preview is False


def test_cases_use_parse_for_valid_refusal_and_incomplete_modes() -> None:
    client = FakeClient()

    for case in spike.build_cases():
        spike.run_case(
            client,
            case,
            model="local-model",
            timeout_seconds=1.0,
            trace_id="trace-test",
            show_raw_preview=False,
        )

    call_names = [name for name, _ in client.responses.calls]
    assert call_names == ["parse", "create", "parse", "parse"]
    assert client.responses.calls[0][1]["model"] == "local-model"


def test_observation_hides_raw_preview_by_default() -> None:
    response = SimpleNamespace(
        status="completed",
        output_parsed=None,
        output_text="secret raw provider text",
    )

    lines = spike.observation_lines(
        case_name="case",
        trace_id="trace-1",
        request_mode="responses.create",
        response=response,
        show_raw_preview=False,
    )

    assert "raw_preview:" not in "\n".join(lines)
    assert any(line == "raw_fallback_text_present: yes" for line in lines)


def test_observation_raw_preview_is_bounded_when_enabled() -> None:
    response = SimpleNamespace(
        status="completed",
        output_parsed=None,
        output_text="x" * 400,
    )

    lines = spike.observation_lines(
        case_name="case",
        trace_id="trace-1",
        request_mode="responses.create",
        response=response,
        show_raw_preview=True,
    )

    preview_line = next(line for line in lines if line.startswith("raw_preview: "))
    assert len(preview_line.removeprefix("raw_preview: ")) <= spike.RAW_PREVIEW_LIMIT


def test_pydantic_validation_error_does_not_leak_raw_provider_text() -> None:
    secret_provider_text = "secret raw provider text"
    try:
        spike.SpikeStructuredResult.model_validate_json(secret_provider_text)
    except Exception as exc:
        lines = spike.error_observation_lines(
            case_name="case",
            trace_id="trace-1",
            request_mode="responses.parse",
            error=exc,
        )
    else:
        raise AssertionError("expected validation error")

    output = "\n".join(lines)
    assert secret_provider_text not in output
    assert "validation failed" in output
