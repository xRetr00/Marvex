from __future__ import annotations

from datetime import datetime
from typing import Any

from packages.contracts import (
    AssistantInputSource,
    AssistantMode,
    AssistantTurnInput,
    InputEvent,
    InputModality,
    IdentityRef,
    PolicyContext,
    Privacy,
    Sensitivity,
    SessionRef,
    TextPayload,
)


def build_text_input_event(
    *,
    schema_version: str,
    trace_id: str,
    event_id: str,
    text: str,
    timestamp: datetime,
    source: AssistantInputSource = AssistantInputSource.CLI,
    session_id: str | None = None,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
    redaction_needed: bool = False,
    metadata: dict[str, Any] | None = None,
) -> InputEvent:
    return InputEvent(
        schema_version=schema_version,
        trace_id=trace_id,
        event_id=event_id,
        source=source,
        input_modality=InputModality.TEXT,
        payload=TextPayload(kind="text", text=text),
        payload_ref=None,
        session_ref=(
            SessionRef(ref_type="session", ref_id=session_id)
            if session_id is not None
            else None
        ),
        privacy=Privacy(sensitivity=sensitivity, redaction_needed=redaction_needed),
        timestamp=timestamp,
        metadata=dict(metadata or {}),
    )


def build_turn_input_from_event(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    input_event: InputEvent,
    identity_id: str | None = None,
    assistant_mode: AssistantMode = AssistantMode.DEFAULT,
    requested_capabilities: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AssistantTurnInput:
    if input_event.trace_id != trace_id:
        raise ValueError("input_event trace_id must match AssistantTurnInput trace_id")

    return AssistantTurnInput(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        input_event_id=input_event.event_id,
        session_ref=input_event.session_ref,
        identity_ref=(
            IdentityRef(ref_type="identity", ref_id=identity_id)
            if identity_id is not None
            else None
        ),
        user_visible_input=(
            input_event.payload.text if input_event.payload is not None else None
        ),
        assistant_mode=assistant_mode,
        policy_context=PolicyContext(
            requested_capabilities=list(requested_capabilities or []),
            sensitivity=input_event.privacy.sensitivity,
        ),
        metadata=dict(metadata or {}),
    )
