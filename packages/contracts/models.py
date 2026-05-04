from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import (
    AssistantFinishReason,
    AssistantInputSource,
    AssistantMode,
    AssistantResponseType,
    ErrorCode,
    FinishReason,
    HealthStatus,
    InputModality,
    OutputChannelIntent,
    ResponseType,
    Sensitivity,
    Source,
    StageStatus,
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
    previous_response_id: NonEmptyString | None
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


class TextPayload(ContractModel):
    kind: Literal["text"]
    text: str


class PayloadRef(ContractModel):
    ref_type: Literal["payload"]
    ref_id: NonEmptyString = Field(..., min_length=1)
    kind: Literal["text"]
    uri: str | None

    @field_validator("uri")
    @classmethod
    def _validate_local_uri(cls, uri: str | None) -> str | None:
        if uri is None:
            return None
        if not uri.strip():
            raise ValueError("payload_ref uri must be null or a local URI")
        if uri != uri.strip():
            raise ValueError("payload_ref uri must not include surrounding whitespace")
        if not uri.lower().startswith("local://"):
            raise ValueError("payload_ref uri must be local and non-provider")
        return uri


class SessionRef(ContractModel):
    ref_type: Literal["session"]
    ref_id: NonEmptyString = Field(..., min_length=1)


class IdentityRef(ContractModel):
    ref_type: Literal["identity"]
    ref_id: NonEmptyString = Field(..., min_length=1)


class ToolResultRef(ContractModel):
    ref_type: Literal["tool_result"]
    ref_id: NonEmptyString = Field(..., min_length=1)


class MemoryResultRef(ContractModel):
    ref_type: Literal["memory_result"]
    ref_id: NonEmptyString = Field(..., min_length=1)


class OutputEventRef(ContractModel):
    ref_type: Literal["output_event"]
    ref_id: NonEmptyString = Field(..., min_length=1)


class SessionResultRef(ContractModel):
    ref_type: Literal["session_result"]
    ref_id: NonEmptyString = Field(..., min_length=1)


class ProviderTurnRef(ContractModel):
    ref_type: Literal["provider_turn"]
    ref_id: NonEmptyString = Field(..., min_length=1)
    stage_name: NonEmptyString = Field(..., min_length=1)
    provider_name: NonEmptyString = Field(..., min_length=1)
    status: StageStatus
    trace_id: NonEmptyString = Field(..., min_length=1)


class Privacy(ContractModel):
    sensitivity: Sensitivity
    redaction_needed: bool


class PolicyContext(ContractModel):
    requested_capabilities: list[NonEmptyString]
    sensitivity: Sensitivity


class StageSummary(ContractModel):
    stage_name: NonEmptyString = Field(..., min_length=1)
    status: StageStatus
    started_at: datetime | None
    completed_at: datetime | None
    ref: NonEmptyString | None
    error_ref: NonEmptyString | None


class AssistantFinalResponse(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    response_type: AssistantResponseType
    text: str | None
    payload_ref: PayloadRef | None
    output_channel_intent: OutputChannelIntent
    safe_for_display: bool
    safe_for_speech: bool
    memory_write_candidate_hint: bool
    finish_reason: AssistantFinishReason
    metadata: JsonObject

    @model_validator(mode="after")
    def _validate_content_carrier(self) -> AssistantFinalResponse:
        if self.response_type == AssistantResponseType.TEXT:
            if self.text is None or not self.text.strip():
                raise ValueError("text response requires text")
            if self.payload_ref is not None:
                raise ValueError("text response must not include payload_ref")
        if self.response_type == AssistantResponseType.PAYLOAD_REF:
            if self.payload_ref is None:
                raise ValueError("payload_ref response requires payload_ref")
        if (
            self.response_type == AssistantResponseType.ERROR
            and (self.text is None or not self.text.strip())
        ):
            raise ValueError("error response requires user-safe text")
        return self


class InputEvent(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    event_id: NonEmptyString = Field(..., min_length=1)
    source: AssistantInputSource
    input_modality: InputModality
    payload: TextPayload | None
    payload_ref: PayloadRef | None
    session_ref: SessionRef | None
    privacy: Privacy
    timestamp: datetime
    metadata: JsonObject

    @model_validator(mode="after")
    def _validate_payload_carrier(self) -> InputEvent:
        if (self.payload is None) == (self.payload_ref is None):
            raise ValueError("exactly one of payload or payload_ref must be non-null")
        return self


class AssistantTurnInput(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    turn_id: NonEmptyString = Field(..., min_length=1)
    input_event_id: NonEmptyString = Field(..., min_length=1)
    session_ref: SessionRef | None
    identity_ref: IdentityRef | None
    user_visible_input: str | None
    assistant_mode: AssistantMode
    policy_context: PolicyContext
    metadata: JsonObject


class AssistantTurnResult(ContractModel):
    schema_version: NonEmptyString = Field(..., min_length=1)
    trace_id: NonEmptyString = Field(..., min_length=1)
    turn_id: NonEmptyString = Field(..., min_length=1)
    assistant_final_response: AssistantFinalResponse | None
    output_events: list[OutputEventRef]
    stage_summaries: list[StageSummary]
    provider_turn_refs: list[ProviderTurnRef]
    tool_result_refs: list[ToolResultRef]
    memory_result_refs: list[MemoryResultRef]
    session_result_ref: SessionResultRef | None
    error: ErrorEnvelope | None
    metadata: JsonObject

    @model_validator(mode="after")
    def _validate_final_response_or_error(self) -> AssistantTurnResult:
        if self.assistant_final_response is None and self.error is None:
            raise ValueError("assistant_final_response may be null only when error is non-null")
        return self
