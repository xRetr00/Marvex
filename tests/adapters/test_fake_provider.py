from pathlib import Path

from packages.contracts import (
    ErrorCode,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
)
from packages.adapters.providers.fake import (
    FakeProvider,
    FakeProviderConfig,
    FakeProviderMode,
)


def make_request(previous_response_id: str | None = "prev-001") -> ProviderRequest:
    return ProviderRequest(
        schema_version="0.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        model="test-model",
        input_text="Hello",
        instructions=None,
        previous_response_id=previous_response_id,
        provider_options={},
    )


def test_success_response_validates_as_provider_response():
    response = FakeProvider().send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.provider_name == "fake"
    assert validated.schema_version == "0.1-draft"
    assert validated.trace_id == "trace-001"
    assert validated.turn_id == "turn-001"
    assert validated.finish_reason == FinishReason.STOP
    assert validated.error is None


def test_configured_output_text_and_response_id_are_used():
    provider = FakeProvider(
        FakeProviderConfig(output_text="configured text", response_id="resp-custom")
    )

    response = provider.send(make_request())

    assert response.output_text == "configured text"
    assert response.response_id == "resp-custom"


def test_response_id_none_is_allowed():
    provider = FakeProvider(FakeProviderConfig(response_id=None))

    response = provider.send(make_request())

    assert response.response_id is None
    assert ProviderResponse.model_validate(response.model_dump()).response_id is None


def test_error_response_validates_as_provider_response():
    provider = FakeProvider(
        FakeProviderConfig(
            mode=FakeProviderMode.ERROR,
            error_code=ErrorCode.PROVIDER_TIMEOUT,
            error_message="Configured failure.",
        )
    )

    response = provider.send(make_request())

    validated = ProviderResponse.model_validate(response.model_dump())
    assert validated.output_text == ""
    assert validated.finish_reason == FinishReason.ERROR
    assert validated.error is not None
    assert validated.error.code == ErrorCode.PROVIDER_TIMEOUT
    assert validated.error.message == "Configured failure."
    assert validated.error.trace_id == "trace-001"


def test_previous_response_id_is_recorded_when_present():
    response = FakeProvider().send(make_request(previous_response_id="prev-xyz"))

    assert response.raw_metadata == {"previous_response_id": "prev-xyz"}


def test_previous_response_id_none_is_recorded():
    response = FakeProvider().send(make_request(previous_response_id=None))

    assert response.raw_metadata == {"previous_response_id": None}


def test_output_is_deterministic_for_same_request_and_config():
    provider = FakeProvider(
        FakeProviderConfig(output_text="same", response_id="same-response")
    )
    request = make_request()

    first = provider.send(request)
    second = provider.send(request)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_fake_provider_source_has_no_forbidden_implementation_tokens():
    source = (
        Path("packages")
        / "adapters"
        / "providers"
        / "fake"
        / "fake_provider.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = [
        "ht" + "tpx",
        "req" + "uests",
        "url" + "lib",
        "soc" + "ket",
        "sub" + "process",
        "open" + "(",
        "lm" + "studio",
        "orches" + "trat",
        "memory",
        "intent",
        "voice",
        "desktop",
    ]

    assert [token for token in forbidden if token in source] == []
