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


def test_provider_runtime_config_supports_additive_connection_fields():
    from dataclasses import FrozenInstanceError, fields

    from packages.provider_runtime import ProviderRuntimeConfig

    config = ProviderRuntimeConfig(provider_name="fake")

    assert [field.name for field in fields(ProviderRuntimeConfig)] == [
        "provider_name",
        "lmstudio_responses_api_key",
        "litellm_api_key",
        "base_url",
        "provider_mode",
        "timeout_seconds",
    ]
    assert config.base_url is None
    assert config.timeout_seconds is None
    with pytest.raises(FrozenInstanceError):
        config.provider_name = "litellm"


def test_create_lmstudio_provider_receives_base_url_timeout_and_api_key():
    from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(
        ProviderRuntimeConfig(
            provider_name="lmstudio_responses",
            lmstudio_responses_api_key="fake-lmstudio-token-for-test",
            base_url="http://127.0.0.1:1234/v1",
            timeout_seconds=12.5,
        )
    )

    assert isinstance(provider, LMStudioResponsesProvider)
    assert provider._client_kwargs() == {
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "fake-lmstudio-token-for-test",
        "timeout": 12.5,
    }


def test_create_litellm_provider_receives_base_url_timeout_and_api_key():
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(
        ProviderRuntimeConfig(
            provider_name="litellm",
            litellm_api_key="sk-test-litellm",
            base_url="http://127.0.0.1:4000",
            timeout_seconds=9,
        )
    )

    assert isinstance(provider, LiteLLMProvider)
    assert provider._config.api_key == "sk-test-litellm"
    assert provider._config.base_url == "http://127.0.0.1:4000"
    assert provider._config.timeout_seconds == 9


def test_create_litellm_provider_normalizes_native_base_url_to_proxy_mode():
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(
        ProviderRuntimeConfig(
            provider_name="litellm",
            litellm_api_key="sk-test-litellm",
            base_url="https://openrouter.ai/api/v1/",
            provider_mode="native",
        )
    )

    assert isinstance(provider, LiteLLMProvider)
    assert provider._config.base_url == "https://openrouter.ai/api/v1/"
    assert provider._config.provider_mode == "litellm_proxy"


def test_create_litellm_provider_normalizes_google_ai_studio_openai_base_url_to_sdk_mode():
    from packages.adapters.providers.litellm import LiteLLMProvider
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    provider = create_provider(
        ProviderRuntimeConfig(
            provider_name="litellm",
            litellm_api_key="gemini-api-key-for-test",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    )

    assert isinstance(provider, LiteLLMProvider)
    assert provider._config.api_key == "gemini-api-key-for-test"
    assert provider._config.base_url is None
    assert provider._config.provider_mode == "litellm_sdk"


def test_non_litellm_provider_rejects_litellm_api_key():
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    with pytest.raises(ValueError, match="litellm_api_key is only supported for litellm"):
        create_provider(ProviderRuntimeConfig(provider_name="fake", litellm_api_key="sk-test"))


def test_fake_provider_rejects_connection_config_fields():
    from packages.provider_runtime import ProviderRuntimeConfig, create_provider

    with pytest.raises(ValueError, match="base_url is only supported"):
        create_provider(ProviderRuntimeConfig(provider_name="fake", base_url="http://x"))

    with pytest.raises(ValueError, match="timeout_seconds is only supported"):
        create_provider(ProviderRuntimeConfig(provider_name="fake", timeout_seconds=1))
