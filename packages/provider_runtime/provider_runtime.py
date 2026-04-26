from dataclasses import dataclass

from packages.adapters.providers.fake import FakeProvider
from packages.adapters.providers.litellm import LiteLLMProvider
from packages.adapters.providers.lmstudio_responses import LMStudioResponsesProvider
from packages.ports.provider import ProviderPort


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    provider_name: str


def create_provider(config: ProviderRuntimeConfig) -> ProviderPort:
    if config.provider_name == "fake":
        return FakeProvider()
    if config.provider_name == "litellm":
        return LiteLLMProvider()
    if config.provider_name == "lmstudio_responses":
        return LMStudioResponsesProvider()
    raise ValueError(f"unsupported provider: {config.provider_name}")
