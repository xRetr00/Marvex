from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.capability_runtime.results import CapabilityResultEnvelope, SafeCapabilityProjection
from packages.version import MARVEX_VERSION as SERVICE_VERSION


SCHEMA_VERSION = "0.1.1-draft"
SERVICE_NAME = "marvex-tool-worker"


class ToolWorkerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolWorkerConfig:
    autonomy_mode: str = "auto_marvex"


class ToolWorkerError(ToolWorkerModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    turn_id: str | None = None
    code: str
    safe_message: str
    raw_error_persisted: Literal[False] = False


class ToolWorkerCommandResult(ToolWorkerModel):
    schema_version: str = SCHEMA_VERSION
    command: Literal["start", "stop", "status", "health", "version", "execute", "run_capability"]
    ok: bool
    trace_id: str
    state: str | None = None
    blocked: bool = False
    result: CapabilityResultEnvelope | None = None
    projection: SafeCapabilityProjection | None = None
    policy_audit: dict[str, object] | None = None
    error: ToolWorkerError | None = None
    metadata: dict[str, object] = {}
