from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import ConfigDict, field_validator

from .models import ContractModel, NonEmptyString


class AssistantStatusKind(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    WORKING = "working"
    USING_TOOLS = "using_tools"
    MCP = "mcp"
    SKILLS = "skills"
    SEARCHING_WEB = "searching_web"
    TALKING = "talking"
    ASKING = "asking"
    NEEDS_APPROVAL = "needs_approval"


class AssistantStateEvent(ContractModel):
    """Safe, derived-scalar loopback state event for the Shell status pill and waveform overlay.

    raw_audio_persisted is always Literal[False] — audio_level is a derived RMS
    scalar (0.0–1.0) only; no raw audio or transcript is stored or transmitted.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: NonEmptyString
    ts: NonEmptyString  # ISO-8601 UTC string
    status: AssistantStatusKind
    detail: str  # short, safe, may be empty
    audio_level: float  # 0.0–1.0, derived RMS scalar only
    session_ref: str | None
    trace_id: str | None
    raw_audio_persisted: Literal[False] = False

    @field_validator("audio_level")
    @classmethod
    def _clamp_audio_level(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("audio_level must be in [0.0, 1.0]")
        return value
