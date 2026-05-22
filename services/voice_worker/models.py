from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.voice_worker_runtime.models import SCHEMA_VERSION


SERVICE_NAME = "marvex-voice-worker"
SERVICE_VERSION = "0.1.0"


class VoiceWorkerServiceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class VoiceWorkerServiceConfig:
    host: str = "127.0.0.1"
    port: int = 8767
    worker_id: str = "local-voice-worker"


class VoiceWorkerServiceCommandResult(VoiceWorkerServiceModel):
    schema_version: str = SCHEMA_VERSION
    command: Literal["start", "stop", "status", "health", "version"]
    ok: bool
    trace_id: str
    state: str | None = None
    metadata: dict[str, object] = {}
