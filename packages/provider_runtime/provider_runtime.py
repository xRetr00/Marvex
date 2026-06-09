from dataclasses import dataclass
from urllib.parse import urlparse

from packages.ports.provider import ProviderPort

FakeProvider = None
LiteLLMConversationStore = None
LiteLLMProvider = None
LiteLLMProviderConfig = None
LMStudioResponsesProvider = None
LMStudioResponsesProviderConfig = None
OpenRouterProvider = None
OpenRouterProviderConfig = None

# Process-singleton conversation store so successive ``create_provider`` calls
# in the same Python process share LiteLLM message history. Without this, each
# new provider instance would forget every prior turn and ``previous_response_id``
# would be effectively ignored for the OpenAI chat-completions surface.
_LITELLM_CONVERSATION_STORE = None


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    provider_name: str
    lmstudio_responses_api_key: str | None = None
    litellm_api_key: str | None = None
    openrouter_api_key: str | None = None
    base_url: str | None = None
    provider_mode: str | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class _StructuredOutputRequestContext:
    schema_version: str
    trace_id: str
    turn_id: str


_STRUCTURED_OUTPUT_PROVIDER_NAMES = frozenset({"litellm", "lmstudio_responses", "openrouter"})


def create_provider(config: ProviderRuntimeConfig) -> ProviderPort:
    _validate_provider_specific_config(config)
    if config.provider_name == "fake":
        provider_class = _fake_provider_class()
        return provider_class()
    if config.provider_name == "litellm":
        provider_class = _litellm_provider_class()
        config_class = _litellm_provider_config_class()
        store = _litellm_conversation_store()
        base_url = _clean_optional_string(config.base_url)
        provider_mode = _clean_optional_string(config.provider_mode)
        if _is_google_ai_studio_openai_base_url(base_url):
            # Google's OpenAI-compatible endpoint documents chat/completions.
            # Marvex's LiteLLM path must stay Responses-API based, so route
            # Google AI Studio through LiteLLM SDK translation instead.
            base_url = None
            provider_mode = "litellm_sdk"
        elif base_url is not None and provider_mode in {None, "native", "litellm_sdk"}:
            provider_mode = "litellm_proxy"
        provider_config_kwargs = {
            "api_key": _clean_optional_string(config.litellm_api_key),
            "base_url": base_url,
            "provider_mode": provider_mode,
            "timeout_seconds": config.timeout_seconds,
        }
        provider_config_kwargs = {
            key: value for key, value in provider_config_kwargs.items() if value is not None
        }
        if provider_config_kwargs:
            return provider_class(
                config_class(**provider_config_kwargs),
                conversation_store=store,
            )
        return provider_class(conversation_store=store)
    if config.provider_name == "lmstudio_responses":
        provider_class = _lmstudio_responses_provider_class()
        config_class = _lmstudio_responses_provider_config_class()
        provider_config_kwargs = {}
        if _has_lmstudio_responses_api_key(config):
            provider_config_kwargs["api_key"] = str(config.lmstudio_responses_api_key)
        base_url = _clean_optional_string(config.base_url)
        if base_url is not None:
            provider_config_kwargs["base_url"] = base_url
        if config.timeout_seconds is not None:
            provider_config_kwargs["timeout"] = config.timeout_seconds
        if provider_config_kwargs:
            return provider_class(
                config=config_class(**provider_config_kwargs)
            )
        return provider_class()
    if config.provider_name == "openrouter":
        provider_class = _openrouter_provider_class()
        config_class = _openrouter_provider_config_class()
        provider_config_kwargs = {}
        if _has_openrouter_api_key(config):
            provider_config_kwargs["api_key"] = str(config.openrouter_api_key)
        if config.timeout_seconds is not None:
            provider_config_kwargs["timeout_seconds"] = config.timeout_seconds
        if provider_config_kwargs:
            return provider_class(config_class(**provider_config_kwargs))
        return provider_class()
    raise ValueError(f"unsupported provider: {config.provider_name}")


def _fake_provider_class():
    global FakeProvider
    if FakeProvider is None:
        from packages.adapters.providers.fake import FakeProvider
    return FakeProvider


def _litellm_provider_class():
    global LiteLLMProvider
    if LiteLLMProvider is None:
        from packages.adapters.providers.litellm import LiteLLMProvider
    return LiteLLMProvider


def _litellm_conversation_store_class():
    global LiteLLMConversationStore
    if LiteLLMConversationStore is None:
        from packages.adapters.providers.litellm import LiteLLMConversationStore
    return LiteLLMConversationStore


def _litellm_conversation_store():
    """Return the process-singleton LiteLLM conversation store.

    Single instance so chat history survives across ``create_provider`` calls
    within one core-service process.
    """

    global _LITELLM_CONVERSATION_STORE
    if _LITELLM_CONVERSATION_STORE is None:
        _LITELLM_CONVERSATION_STORE = _litellm_conversation_store_class()()
    return _LITELLM_CONVERSATION_STORE


def _litellm_provider_config_class():
    global LiteLLMProviderConfig
    if LiteLLMProviderConfig is None:
        from packages.adapters.providers.litellm import LiteLLMProviderConfig
    return LiteLLMProviderConfig


def _lmstudio_responses_provider_class():
    global LMStudioResponsesProvider
    if LMStudioResponsesProvider is None:
        from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
    return LMStudioResponsesProvider


def _lmstudio_responses_provider_config_class():
    global LMStudioResponsesProviderConfig
    if LMStudioResponsesProviderConfig is None:
        from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProviderConfig
    return LMStudioResponsesProviderConfig


def _openrouter_provider_class():
    global OpenRouterProvider
    if OpenRouterProvider is None:
        from packages.adapters.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider


def _openrouter_provider_config_class():
    global OpenRouterProviderConfig
    if OpenRouterProviderConfig is None:
        from packages.adapters.providers.openrouter import OpenRouterProviderConfig
    return OpenRouterProviderConfig


def _validate_provider_specific_config(config: ProviderRuntimeConfig) -> None:
    if config.provider_name != "lmstudio_responses" and _has_lmstudio_responses_api_key(
        config
    ):
        raise ValueError(
            "lmstudio_responses_api_key is only supported for lmstudio_responses"
        )
    if config.provider_name != "litellm" and _has_litellm_api_key(config):
        raise ValueError("litellm_api_key is only supported for litellm")
    if config.provider_name != "openrouter" and _has_openrouter_api_key(config):
        raise ValueError("openrouter_api_key is only supported for openrouter")
    if config.provider_name == "fake" and _clean_optional_string(config.base_url) is not None:
        raise ValueError("base_url is only supported for network provider adapters")
    if config.provider_name == "fake" and config.timeout_seconds is not None:
        raise ValueError("timeout_seconds is only supported for network provider adapters")
    if config.timeout_seconds is not None and config.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if config.provider_name == "fake" and _clean_optional_string(config.provider_mode) is not None:
        raise ValueError("provider_mode is only supported for network provider adapters")


def _has_lmstudio_responses_api_key(config: ProviderRuntimeConfig) -> bool:
    value = config.lmstudio_responses_api_key
    return isinstance(value, str) and bool(value.strip())


def _has_litellm_api_key(config: ProviderRuntimeConfig) -> bool:
    value = config.litellm_api_key
    return isinstance(value, str) and bool(value.strip())


def _has_openrouter_api_key(config: ProviderRuntimeConfig) -> bool:
    value = config.openrouter_api_key
    return isinstance(value, str) and bool(value.strip())


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _is_google_ai_studio_openai_base_url(value: str | None) -> bool:
    if value is None:
        return False
    parsed = urlparse(value.strip())
    return (
        parsed.scheme in {"http", "https"}
        and parsed.netloc.lower() == "generativelanguage.googleapis.com"
        and "openai" in parsed.path.rstrip("/").lower().split("/")
    )


def map_provider_raw_output_to_structured_result(
    *,
    config: ProviderRuntimeConfig,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    raw_output_text: str,
    target_model: type[object],
    include_raw_preview: bool = False,
) -> object:
    provider = create_provider(config)
    if config.provider_name not in _STRUCTURED_OUTPUT_PROVIDER_NAMES:
        raise ValueError(f"unsupported structured output provider: {config.provider_name}")

    map_raw_output = getattr(provider, "map_raw_output_to_structured_result", None)
    if not callable(map_raw_output):
        raise ValueError(f"unsupported structured output provider: {config.provider_name}")

    return map_raw_output(
        request=_StructuredOutputRequestContext(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
        ),
        raw_output_text=raw_output_text,
        target_contract=target_contract,
        target_model=target_model,
        include_raw_preview=include_raw_preview,
    )
