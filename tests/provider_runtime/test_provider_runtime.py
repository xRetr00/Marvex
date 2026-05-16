import pytest

from packages.ports.provider import ProviderPort


def test_create_fake_provider_returns_provider_port_compatible_provider():
    from packages.adapters.providers.fake import FakeProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(ProviderRuntimeConfig(provider_name="fake"))

    assert isinstance(provider, ProviderPort)
    assert isinstance(provider, FakeProvider)


def test_create_litellm_provider_returns_provider_port_compatible_provider():
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(ProviderRuntimeConfig(provider_name="litellm"))

    assert isinstance(provider, ProviderPort)
    assert isinstance(provider, LiteLLMProvider)


def test_create_lmstudio_responses_provider_returns_provider_port_compatible_provider():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(ProviderRuntimeConfig(provider_name="lmstudio_responses"))

    assert isinstance(provider, ProviderPort)
    assert isinstance(provider, LMStudioResponsesProvider)


def test_create_lmstudio_responses_provider_accepts_lmstudio_specific_fake_api_key():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(
        ProviderRuntimeConfig(
            provider_name="lmstudio_responses",
            lmstudio_responses_api_key="fake-lmstudio-token-for-test",
        )
    )

    assert isinstance(provider, LMStudioResponsesProvider)
    assert provider._client_kwargs()["api_key"] == "fake-lmstudio-token-for-test"


def test_non_lmstudio_provider_rejects_lmstudio_specific_api_key():
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    with pytest.raises(
        ValueError,
        match="lmstudio_responses_api_key is only supported for lmstudio_responses",
    ):
        create_provider(
            ProviderRuntimeConfig(
                provider_name="fake",
                lmstudio_responses_api_key="fake-lmstudio-token-for-test",
            )
        )


def test_unknown_provider_fails_clearly():
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    with pytest.raises(ValueError, match="unsupported provider: unknown"):
        create_provider(ProviderRuntimeConfig(provider_name="unknown"))


def test_provider_runtime_config_is_frozen_and_provider_name_only():
    from dataclasses import FrozenInstanceError, fields

    from packages.provider_runtime import ProviderRuntimeConfig

    config = ProviderRuntimeConfig(provider_name="fake")

    assert [field.name for field in fields(ProviderRuntimeConfig)] == [
        "provider_name",
        "lmstudio_responses_api_key",
    ]
    with pytest.raises(FrozenInstanceError):
        config.provider_name = "litellm"
