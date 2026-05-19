from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel


class VoiceErrorEnvelope(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str = Field(..., min_length=1)
    error_id: str = Field(..., min_length=1)
    code: Literal["VOICE_BACKEND_ERROR", "VOICE_POLICY_BLOCK", "VOICE_VALIDATION_ERROR"]
    message: str = Field(..., min_length=1)
    recoverable: bool = True
    source: str = "voice_runtime"
    details: dict[str, str]
    raw_backend_error_persisted: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def backend_error(cls, *, trace_id: str, backend_id: str, reason_code: str) -> "VoiceErrorEnvelope":
        return cls(
            trace_id=trace_id,
            error_id=f"voice.backend.{backend_id}.{reason_code}",
            code="VOICE_BACKEND_ERROR",
            message="Voice backend request failed safely.",
            details={"reason_code": reason_code, "backend_id": backend_id},
        )

    @classmethod
    def policy_block(cls, *, trace_id: str, reason_code: str) -> "VoiceErrorEnvelope":
        return cls(
            trace_id=trace_id,
            error_id=f"voice.policy.{reason_code}",
            code="VOICE_POLICY_BLOCK",
            message="Voice request requires policy handling before execution.",
            details={"reason_code": reason_code},
            recoverable=True,
        )

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump(mode="json")
