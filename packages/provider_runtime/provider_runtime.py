from dataclasses import dataclass

from packages.adapters.providers.fake import FakeProvider
from packages.adapters.providers.litellm import LiteLLMProvider
from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProviderConfig
from packages.ports.provider import ProviderPort


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    provider_name: str
    lmstudio_responses_api_key: str | None = None


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
        return LiteLLMProvider()
    if config.provider_name == "lmstudio_responses":
        if _has_lmstudio_responses_api_key(config):
            return LMStudioResponsesProvider(
                config=LMStudioResponsesProviderConfig(
                    api_key=str(config.lmstudio_responses_api_key)
                )
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


def _has_lmstudio_responses_api_key(config: ProviderRuntimeConfig) -> bool:
    value = config.lmstudio_responses_api_key
    return isinstance(value, str) and bool(value.strip())


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
