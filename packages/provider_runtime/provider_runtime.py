from dataclasses import dataclass

from packages.adapters.providers.fake import FakeProvider
from packages.adapters.providers.litellm import LiteLLMProvider
from packages.adapters.providers.litellm import LiteLLMProviderConfig
from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProviderConfig
from packages.ports.provider import ProviderPort


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    provider_name: str
    lmstudio_responses_api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class _StructuredOutputRequestContext:
    schema_version: str
    trace_id: str
    turn_id: str


_STRUCTURED_OUTPUT_PROVIDER_NAMES = frozenset({"litellm", "lmstudio_responses"})


def create_provider(config: ProviderRuntimeConfig) -> ProviderPort:
    _validate_provider_specific_config(config)
    if config.provider_name == "fake":
        return FakeProvider()
    if config.provider_name == "litellm":
        provider_config_kwargs = {
            "base_url": _clean_optional_string(config.base_url),
            "timeout_seconds": config.timeout_seconds,
        }
        provider_config_kwargs = {
            key: value for key, value in provider_config_kwargs.items() if value is not None
        }
        if provider_config_kwargs:
            return LiteLLMProvider(
                LiteLLMProviderConfig(
                    **provider_config_kwargs,
                )
            )
        return LiteLLMProvider()
    if config.provider_name == "lmstudio_responses":
        provider_config_kwargs = {}
        if _has_lmstudio_responses_api_key(config):
            provider_config_kwargs["api_key"] = str(config.lmstudio_responses_api_key)
        base_url = _clean_optional_string(config.base_url)
        if base_url is not None:
            provider_config_kwargs["base_url"] = base_url
        if config.timeout_seconds is not None:
            provider_config_kwargs["timeout"] = config.timeout_seconds
        if provider_config_kwargs:
            return LMStudioResponsesProvider(
                config=LMStudioResponsesProviderConfig(**provider_config_kwargs)
            )
        return LMStudioResponsesProvider()
    raise ValueError(f"unsupported provider: {config.provider_name}")


def _validate_provider_specific_config(config: ProviderRuntimeConfig) -> None:
    if config.provider_name != "lmstudio_responses" and _has_lmstudio_responses_api_key(
        config
    ):
        raise ValueError(
            "lmstudio_responses_api_key is only supported for lmstudio_responses"
        )
    if config.provider_name == "fake" and _clean_optional_string(config.base_url) is not None:
        raise ValueError("base_url is only supported for network provider adapters")
    if config.provider_name == "fake" and config.timeout_seconds is not None:
        raise ValueError("timeout_seconds is only supported for network provider adapters")
    if config.timeout_seconds is not None and config.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")


def _has_lmstudio_responses_api_key(config: ProviderRuntimeConfig) -> bool:
    value = config.lmstudio_responses_api_key
    return isinstance(value, str) and bool(value.strip())


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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
