from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.contracts import ErrorEnvelope, ProviderResponse


SCHEMA_VERSION = "0.1.1-draft"
SERVICE_NAME = "marvex-provider-worker"
SERVICE_VERSION = "0.2.0"


class ProviderWorkerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ProviderWorkerConfig:
    provider_candidates: tuple[str, ...] = ("lmstudio_responses", "litellm")
    fallback_enabled: bool = True
    max_retries: int = 0
    unavailable_provider_ids: tuple[str, ...] = ()


class ProviderWorkerSelectionProjection(ProviderWorkerModel):
    selected_provider_id: str
    fallback_provider_ids: tuple[str, ...]
    rejected_provider_ids: tuple[str, ...]
    fallback_allowed: bool
    retry_allowed: bool


class ProviderWorkerCommandResult(ProviderWorkerModel):
    schema_version: str = SCHEMA_VERSION
    command: Literal["start", "stop", "status", "health", "version", "send", "structured_output"]
    ok: bool
    trace_id: str
    state: str | None = None
    response: ProviderResponse | None = None
    error: ErrorEnvelope | None = None
    selection: ProviderWorkerSelectionProjection | None = None
    metadata: dict[str, object] = {}
