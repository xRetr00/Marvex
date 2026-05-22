from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.desktop_agent_runtime.models import DesktopPerceptionSnapshot, DesktopRecallResult


SCHEMA_VERSION = "0.1.1-draft"
SERVICE_NAME = "marvex-desktop-agent"
SERVICE_VERSION = "0.1.0"


class DesktopAgentServiceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class DesktopAgentConfig:
    content_budget_chars: int = 1600


class DesktopAgentError(DesktopAgentServiceModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str
    code: str
    safe_message: str
    raw_error_persisted: Literal[False] = False


class DesktopAgentCommandResult(DesktopAgentServiceModel):
    schema_version: str = SCHEMA_VERSION
    command: Literal["start", "stop", "status", "health", "version", "perceive", "recall"]
    ok: bool
    trace_id: str
    state: str | None = None
    snapshot: DesktopPerceptionSnapshot | None = None
    recall: DesktopRecallResult | None = None
    error: DesktopAgentError | None = None
    metadata: dict[str, object] = {}
