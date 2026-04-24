from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ErrorCode,
    FinishReason,
    HealthStatus,
    ResponseType,
    Source,
    TraceLevel,
    TraceStage,
)


JsonObject = dict[str, Any]
NonEmptyString = str


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TurnInput(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    turn_id: NonEmptyString = Field(..., min_length=1)
    input_text: str
    source: Source
    metadata: JsonObject


class FinalResponse(ContractModel):
    text: str
    response_type: ResponseType
    finish_reason: FinishReason
    safe_for_tts: bool
    metadata: JsonObject


class TraceEvent(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    event_id: NonEmptyString = Field(..., min_length=1)
    timestamp: datetime
    stage: TraceStage
    level: TraceLevel
    message: str
    data: JsonObject


class ErrorEnvelope(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    error_id: NonEmptyString = Field(..., min_length=1)
    code: ErrorCode
    message: str
    recoverable: bool
    source: NonEmptyString = Field(..., min_length=1)
    details: JsonObject


class TurnOutput(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    turn_id: NonEmptyString = Field(..., min_length=1)
    final_response: FinalResponse
    provider_response_id: NonEmptyString | None
    events: list[TraceEvent]
    error: ErrorEnvelope | None


class ProviderRequest(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    turn_id: NonEmptyString = Field(..., min_length=1)
    model: NonEmptyString = Field(..., min_length=1)
    input_text: str
    instructions: str | None
    previous_response_id: NonEmptyString | None
    provider_options: JsonObject


class ProviderResponse(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    turn_id: NonEmptyString = Field(..., min_length=1)
    provider_name: NonEmptyString = Field(..., min_length=1)
    response_id: NonEmptyString | None
    output_text: str
    finish_reason: FinishReason
    usage: JsonObject
    raw_metadata: JsonObject
    error: ErrorEnvelope | None


class HealthCheck(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    service: NonEmptyString = Field(..., min_length=1)
    status: HealthStatus
    version: NonEmptyString = Field(..., min_length=1)
    uptime_seconds: float = Field(..., ge=0)
    dependencies: JsonObject


class VersionInfo(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    service: NonEmptyString = Field(..., min_length=1)
    service_version: NonEmptyString = Field(..., min_length=1)
    contract_versions: JsonObject
    build: JsonObject
