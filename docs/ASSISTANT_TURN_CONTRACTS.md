# Assistant Turn Contracts

## Purpose

This document drafts the first assistant-level envelope contracts above the
provider foundation:

- `InputEvent`
- `AssistantTurnInput`
- `AssistantTurnResult`
- `AssistantFinalResponse`

These contracts are draft documentation only.

Do not create Pydantic models from this document until contracts are approved.

## Direct Rules

The provider turn is not the assistant turn.

The provider path is only a foundation/test path.

These draft contracts are not implementation-approved. They cannot be used by
runtime code, Core, CLI, ProviderRuntime, adapters, services, or tests as active
models until `docs/CONTRACT_APPROVALS.md` marks them `approved` with
`implementation_allowed: yes`.

No assistant data may be hidden in provider-foundation extension fields.

## Relationship To Provider Foundation

TurnInput and TurnOutput remain provider-foundation contracts.

FinalResponse remains provider-foundation final response until explicitly migrated or wrapped.

ProviderRequest and ProviderResponse remain provider-only.

InputEvent and AssistantTurnInput sit above provider calls.

AssistantTurnResult may reference provider TurnOutput or provider-stage summaries.

AssistantFinalResponse owns assistant-level user-facing response.

TraceEvent and ErrorEnvelope remain shared base contracts.

Provider-foundation contracts must not be silently reclassified as assistant
contracts. Assistant-level contracts may wrap or reference provider-foundation
contracts, but must not mutate them into assistant contracts.

## Draft Common Rules

- All objects are JSON-compatible.
- `schema_version` is required and non-empty.
- `trace_id` is required and non-empty where listed.
- `turn_id` is required and non-empty where listed.
- Required fields must be present even when their value is `null`.
- Nullable fields are explicitly documented as nullable.
- Unknown fields are allowed only inside metadata.
- Objects must be JSON objects, not encoded JSON strings.
- Timestamps must use ISO 8601 UTC.
- Id fields must be non-empty strings.
- Examples use active schema version `0.1.1-draft`.

## InputEvent

Purpose: Normalize external input from CLI, future Shell, Voice, Desktop, and
proactive triggers before assistant turn entry.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `event_id`: string, required, non-empty.
- `source`: string enum, required. Draft values include `cli`, `shell`, `voice`, `desktop`, `proactive`.
- `input_modality`: string enum, required. Draft values include `text`, `voice`, `desktop`, `system`.
- `payload`: object or null, required, nullable. Carries normalized input content, not raw UI, voice, desktop, or provider blobs.
- `payload_ref`: string or null, required, nullable. References externally stored payload content when `payload` is omitted or too large.
- `session_ref`: string or null, required, nullable. References future session state without embedding session body.
- `privacy`: object, required, may be empty. Carries local privacy/security classification metadata.
- `timestamp`: string, required, ISO 8601 UTC.
- `metadata`: object, required, may be empty.

Draft rules:

- The payload and payload_ref relationship is explicit: at least one of `payload` or `payload_ref` must be non-null in a future approved schema.
- Text input is represented as normalized `payload` content and does not require voice, UI, desktop, or proactive implementation.
- `InputEvent` must not be a raw unnormalized UI/voice/blob dump.
- Must not include provider request fields.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "event_id": "event-001",
  "source": "cli",
  "input_modality": "text",
  "payload": {
    "text": "Hello"
  },
  "payload_ref": null,
  "session_ref": null,
  "privacy": {},
  "timestamp": "2026-05-01T12:00:00Z",
  "metadata": {}
}
```

## AssistantTurnInput

Purpose: Assistant-level turn entry after input normalization.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `turn_id`: string, required, non-empty.
- `input_event_id`: string, required, non-empty.
- `session_ref`: string or null, required, nullable.
- `identity_ref`: string or null, required, nullable.
- `user_visible_input`: string or null, required, nullable.
- `assistant_mode`: string, required, non-empty. Draft examples include `default`.
- `policy_context`: object, required, may be empty. Carries policy seed values, not policy decisions.
- `metadata`: object, required, may be empty.

Draft rules:

- Must not alias TurnInput.
- Provider-foundation turn compatibility, if needed later, must use explicit fields or references approved for that purpose, not metadata.
- Must not carry provider-specific options.
- Must not contain memory/tool/session bodies directly.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "turn_id": "turn-001",
  "input_event_id": "event-001",
  "session_ref": null,
  "identity_ref": null,
  "user_visible_input": "Hello",
  "assistant_mode": "default",
  "policy_context": {},
  "metadata": {}
}
```

## AssistantTurnResult

Purpose: Complete assistant-level turn result, independent of whether provider
calls happened.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `turn_id`: string, required, non-empty.
- `assistant_final_response`: AssistantFinalResponse or null, required, nullable.
- `output_events`: array, required, may be empty. Future `OutputEvent` items require separate approval.
- `stage_summaries`: array, required, may be empty. Contains stage summaries, not raw subsystem bodies.
- `provider_turn_refs`: array, required, may be empty. References provider turns or provider-stage summaries when provider calls occur.
- `tool_result_refs`: array, required, may be empty. References future tool results without embedding raw outputs.
- `memory_result_refs`: array, required, may be empty. References future memory results without embedding raw memory contents.
- `session_result_ref`: string or null, required, nullable.
- `error`: ErrorEnvelope or null, required, nullable.
- `metadata`: object, required, may be empty.

Draft rules:

- Must not be shaped around provider_response_id.
- Must be valid even if no provider call happened.
- Provider turn references are references or summaries, not the central result shape.
- Must not embed raw tool/memory outputs unless a future approved contract allows it.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "turn_id": "turn-001",
  "assistant_final_response": {
    "schema_version": "0.1.1-draft",
    "response_type": "text",
    "text": "Hello.",
    "payload_ref": null,
    "output_channel_intent": "default",
    "safe_for_display": true,
    "safe_for_speech": true,
    "memory_write_eligible": false,
    "finish_reason": "stop",
    "metadata": {}
  },
  "output_events": [],
  "stage_summaries": [],
  "provider_turn_refs": [],
  "tool_result_refs": [],
  "memory_result_refs": [],
  "session_result_ref": null,
  "error": null,
  "metadata": {}
}
```

## AssistantFinalResponse

Purpose: User-facing assistant response independent of provider response shape.

Fields:

- `schema_version`: string, required, non-empty.
- `response_type`: string enum, required. Draft values include `text`, `error`, `multimodal_ref`.
- `text`: string or null, required, nullable.
- `payload_ref`: string or null, required, nullable.
- `output_channel_intent`: string, required, non-empty. Draft values include `default`, `display`, `speech`.
- `safe_for_display`: boolean, required.
- `safe_for_speech`: boolean, required.
- `memory_write_eligible`: boolean, required.
- `finish_reason`: string enum, required. Draft values include `stop`, `length`, `cancelled`, `error`, `unknown`.
- `metadata`: object, required, may be empty.

Draft rules:

- `AssistantFinalResponse` may wrap the current `FinalResponse` conceptually, but must not become an alias for FinalResponse.
- Text-first behavior is supported without blocking future multimodal or channel-specific output.
- TTS/UI details must not be provider-response fields.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "response_type": "text",
  "text": "Hello.",
  "payload_ref": null,
  "output_channel_intent": "default",
  "safe_for_display": true,
  "safe_for_speech": true,
  "memory_write_eligible": false,
  "finish_reason": "stop",
  "metadata": {}
}
```

## Implementation Block

These four contracts remain draft-only until a future approval task explicitly
changes `docs/CONTRACT_APPROVALS.md`.

Implementation remains blocked while approval status is `draft` and
`implementation_allowed` is `no`.

Forbidden until approval:

- Pydantic models for these contracts
- Core orchestration changes using these contracts
- AssistantTurnRuntime implementation
- provider behavior changes
- CLI behavior changes
- service, HTTP, IPC, or worker runtime behavior
- memory, tools, voice, UI, desktop, or proactive behavior
