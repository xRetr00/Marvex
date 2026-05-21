from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.contracts import ErrorEnvelope
from packages.intent_runtime.models import SafeIntentProjection


SCHEMA_VERSION = "0.1.1-draft"
SERVICE_NAME = "marvex-intent-worker"
SERVICE_VERSION = "0.1.0"
MAX_INPUT_SUMMARY_CHARS = 600


class IntentWorkerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class IntentWorkerConfig:
    max_input_summary_chars: int = MAX_INPUT_SUMMARY_CHARS


class IntentWorkerCommandResult(IntentWorkerModel):
    schema_version: str = SCHEMA_VERSION
    command: Literal["start", "stop", "status", "health", "version", "classify"]
    ok: bool
    trace_id: str
    state: str | None = None
    classification: SafeIntentProjection | None = None
    backend_name: str | None = None
    error: ErrorEnvelope | None = None
    metadata: dict[str, object] = {}
