# Assistant Turn Contracts

## Purpose

This document defines the approved first assistant-level envelope contracts above the
provider foundation:

- `InputEvent`
- `AssistantTurnInput`
- `AssistantTurnResult`
- `AssistantFinalResponse`

These contracts are approved documentation contracts for future implementation.

Pydantic contract models for these contracts live in `packages/contracts/models.py`.

File size justification: this document keeps the four assistant envelope contracts,
their shared reference shapes, examples, and implementation block together so
approval reviewers can evaluate cross-contract semantics in one place.

## Direct Rules

The provider turn is not the assistant turn.

The provider path is only a foundation/test path.

These contracts are approved for future implementation by
`docs/CONTRACT_APPROVALS.md`.

This document does not implement them, create Pydantic models, or change runtime behavior.

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

## Contract Common Rules

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

## Assistant Envelope Enums

These are assistant-envelope enums, not provider-foundation enums.

- source: `cli`, `shell`, `voice`, `desktop`, `proactive`, `system`.
- input_modality: `text`, `speech`, `desktop_event`, `system_event`.
- assistant_mode: `default`, `diagnostic`.
- response_type: `text`, `error`, `payload_ref`.
- output_channel_intent: `default`, `display`, `speech`, `both`.
- finish_reason: `stop`, `length`, `cancelled`, `error`, `unknown`.

These values are closed for the approved assistant envelope contracts. Expanding
any enum requires contract review before implementation.

## Reference Strategy

Hybrid reference strategy:

- Same-envelope ids may remain non-empty strings, such as `input_event_id`.
- Cross-runtime references must be constrained strings or minimal typed references/summaries.
- References must not embed subsystem bodies.
- `payload_ref` must reference normalized payload storage or a future approved
  payload-reference contract.
- `session_ref`, `identity_ref`, `provider_turn_refs`, `tool_result_refs`,
  `memory_result_refs`, `session_result_ref`, and output event references must
  not contain session bodies, identity/profile bodies, raw provider payloads,
  tool output, memory content, UI render payloads, TTS data, or dispatch
  instructions.

`payload_ref` shape:

```json
{
  "ref_type": "payload",
  "ref_id": "payload-001",
  "kind": "text",
  "uri": null
}
```

Rules:

- `ref_type` is closed to `payload`.
- `ref_id` is a non-empty string.
- `kind` is initially `text`.
- `uri` is nullable and must be local/non-provider unless future storage
  contracts approve another location.
- `payload_ref` must not point to arbitrary provider content.

`session_ref` shape:

```json
{
  "ref_type": "session",
  "ref_id": "session-001"
}
```

Rules:

- no session body
- no conversation history
- no provider history

`identity_ref` shape:

```json
{
  "ref_type": "identity",
  "ref_id": "local-profile-001"
}
```

Rules:

- no profile body
- no personal data body

`tool_result_ref` shape:

```json
{
  "ref_type": "tool_result",
  "ref_id": "tool-result-001"
}
```

`memory_result_ref` shape:

```json
{
  "ref_type": "memory_result",
  "ref_id": "memory-result-001"
}
```

`output_event_ref` shape:

```json
{
  "ref_type": "output_event",
  "ref_id": "output-event-001"
}
```

`session_result_ref` shape:

```json
{
  "ref_type": "session_result",
  "ref_id": "session-result-001"
}
```

These reference shapes are minimal. They do not approve the referenced contract
families for implementation.

## Assistant Envelope Schema Version Policy

Approved assistant envelope contracts use `0.1.1-draft` for documentation,
examples, and approval rows.

A distinct assistant envelope schema version may be required before future
breaking contract changes.

No schema version split is approved by these contracts.

## InputEvent

Purpose: Normalize external input from CLI, future Shell, Voice, Desktop, and
proactive triggers before assistant turn entry.

Fields:

- `schema_version`: string, required, non-empty.
- `trace_id`: string, required, non-empty.
- `event_id`: string, required, non-empty.
- `source`: assistant-envelope enum, required. Allowed values: `cli`, `shell`, `voice`, `desktop`, `proactive`, `system`.
- `input_modality`: assistant-envelope enum, required. Allowed values: `text`, `speech`, `desktop_event`, `system_event`.
- `payload`: object or null, required, nullable. For this approved envelope, the only allowed object shape is the minimal normalized text payload.
- `payload_ref`: payload_ref object or null, required, nullable. References normalized payload content and must not point to arbitrary provider content.
- `session_ref`: session_ref object or null, required, nullable. References future session state without embedding session body.
- `privacy`: object, required. Minimal local classification object with required keys `sensitivity` and `redaction_needed`.
- `timestamp`: string, required, ISO 8601 UTC.
- `metadata`: object, required, may be empty.

Minimal normalized text payload:

```json
{
  "kind": "text",
  "text": "Hello"
}
```

Contract rules:

- The payload and payload_ref relationship is explicit.
- Exactly one of `payload` or `payload_ref` must be non-null.
- Both null is invalid.
- Both present is invalid for this approved envelope.
- `payload` is allowed only as a minimal normalized text payload for this approved envelope.
- Raw UI trees, raw audio, screenshots, desktop captures, binary blobs, provider requests, provider responses, and encoded JSON strings are forbidden in `payload`.
- `payload_ref` must not point to arbitrary provider content.
- `InputEvent` must not be a raw unnormalized UI/voice/blob dump.
- Must not include provider request fields.

Privacy rules:

- `privacy` is local classification metadata only.
- Required keys: `sensitivity`, `redaction_needed`.
- sensitivity: `normal`, `sensitive`, `secret`.
- redaction_needed: boolean.
- Policy decisions, access grants, permission results, identity/profile data, and redaction results are forbidden in `privacy`.

Example:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-001",
  "event_id": "event-001",
  "source": "cli",
  "input_modality": "text",
  "payload": {
    "kind": "text",
    "text": "Hello"
  },
  "payload_ref": null,
  "session_ref": null,
  "privacy": {
    "sensitivity": "normal",
    "redaction_needed": false
  },
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
- `session_ref`: session_ref object or null, required, nullable. Reference only; no session body.
- `identity_ref`: identity_ref object or null, required, nullable. Reference only; no identity/profile body.
- `user_visible_input`: string or null, required, nullable.
- `assistant_mode`: assistant-envelope enum, required. Allowed values: `default`, `diagnostic`.
- `policy_context`: object, required. Minimal seed object with required keys `requested_capabilities` and `sensitivity`.
- `metadata`: object, required, may be empty.

Contract rules:

- Must not alias TurnInput.
- Provider-foundation turn compatibility, if needed later, must use explicit fields or references approved for that purpose, not metadata.
- Must not carry provider-specific options.
- Must not contain memory/tool/session bodies directly.
- For text modality, `user_visible_input` must be a non-null string.
- For non-text modalities, `user_visible_input` may be null only when a future approved payload/reference contract supplies a user-visible representation.
- `user_visible_input` must not be used to smuggle raw desktop, voice, UI, or provider data.

Policy context rules:

- `policy_context` is seed-only.
- Required keys: `requested_capabilities`, `sensitivity`.
- Allowed: requested capability labels, sensitivity hints, and other non-decision inputs to PolicyRuntime.
- Requested capabilities are labels only.
- sensitivity uses the same values as `privacy`: `normal`, `sensitive`, `secret`.
- Policy allow/deny results, permission grants, tool scopes, memory write approval, policy engine output, and identity/session bodies are forbidden in `policy_context`.

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
  "policy_context": {
    "requested_capabilities": [],
    "sensitivity": "normal"
  },
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
- `output_events`: array of output_event_ref objects, required, may be empty. Empty or reference/summary only until `OutputEvent` is approved.
- `stage_summaries`: array of minimal stage summary objects, required, may be empty.
- `provider_turn_refs`: array of provider_turn_ref objects, required, may be empty.
- `tool_result_refs`: array of tool_result_ref objects, required, may be empty. References only until `ToolResult` is approved.
- `memory_result_refs`: array of memory_result_ref objects, required, may be empty. References only until `MemoryResult` is approved.
- `session_result_ref`: session_result_ref object or null, required, nullable. Reference only; no session body.
- `error`: ErrorEnvelope or null, required, nullable.
- `metadata`: object, required, may be empty.

Minimal `stage_summaries` item shape:

```json
{
  "stage_name": "provider_reasoning",
  "status": "completed",
  "started_at": null,
  "completed_at": null,
  "ref": null,
  "error_ref": null
}
```

Rules for `stage_summaries`:

- status values: `pending`, `skipped`, `completed`, `degraded`, `failed`, `cancelled`.
- No raw subsystem state, raw provider responses, tool outputs, memory content, prompt text, or hidden context blocks may appear in `stage_summaries`.
- Stage-level failures belong in `stage_summaries` via `status` and `error_ref`.

Minimal `provider_turn_refs` item shape:

```json
{
  "ref_type": "provider_turn",
  "ref_id": "provider-turn-001",
  "stage_name": "provider_reasoning",
  "provider_name": "fake",
  "status": "completed",
  "trace_id": "trace-001"
}
```

Rules for `provider_turn_refs`:

- Provider refs use the same closed status values as stage summaries: `pending`, `skipped`, `completed`, `degraded`, `failed`, `cancelled`.
- No embedded `ProviderRequest`.
- No embedded `ProviderResponse`.
- No central `provider_response_id`.
- No provider routing/fallback/session state.

Reference rules:

- `tool_result_refs` are references only until `ToolResult` is approved.
- `memory_result_refs` are references only until `MemoryResult` is approved.
- `output_events` are empty or reference/summary only until `OutputEvent` is approved.
- No raw tool output, memory content, UI render payload, TTS data, speech audio, or channel dispatch instruction may be embedded.

Error and partial result rules:

- Must not be shaped around provider_response_id.
- Must be valid even if no provider call happened.
- Provider turn references are references or summaries, not the central result shape.
- Must not embed raw tool/memory outputs unless a future approved contract allows it.
- `assistant_final_response` may be null only on hard failure when no user-facing response can be assembled.
- Degraded turns may contain both `assistant_final_response` and `error`.
- Top-level `error` means unrecovered or user-visible turn failure unless a degraded status is explicitly represented.

Example: successful result without provider call:

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
    "memory_write_candidate_hint": false,
    "finish_reason": "stop",
    "metadata": {}
  },
  "output_events": [],
  "stage_summaries": [
    {
      "stage_name": "final_response_assembly",
      "status": "completed",
      "started_at": null,
      "completed_at": null,
      "ref": null,
      "error_ref": null
    }
  ],
  "provider_turn_refs": [],
  "tool_result_refs": [],
  "memory_result_refs": [],
  "session_result_ref": null,
  "error": null,
  "metadata": {}
}
```

Example: successful result with provider ref:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-002",
  "turn_id": "turn-002",
  "assistant_final_response": {
    "schema_version": "0.1.1-draft",
    "response_type": "text",
    "text": "Provider-backed answer.",
    "payload_ref": null,
    "output_channel_intent": "display",
    "safe_for_display": true,
    "safe_for_speech": false,
    "memory_write_candidate_hint": false,
    "finish_reason": "stop",
    "metadata": {}
  },
  "output_events": [],
  "stage_summaries": [
    {
      "stage_name": "provider_reasoning",
      "status": "completed",
      "started_at": null,
      "completed_at": null,
      "ref": "provider-turn-001",
      "error_ref": null
    }
  ],
  "provider_turn_refs": [
    {
      "ref_type": "provider_turn",
      "ref_id": "provider-turn-001",
      "stage_name": "provider_reasoning",
      "provider_name": "fake",
      "status": "completed",
      "trace_id": "trace-002"
    }
  ],
  "tool_result_refs": [],
  "memory_result_refs": [],
  "session_result_ref": null,
  "error": null,
  "metadata": {}
}
```

Example: hard failure without user-facing response:

```json
{
  "schema_version": "0.1.1-draft",
  "trace_id": "trace-003",
  "turn_id": "turn-003",
  "assistant_final_response": null,
  "output_events": [],
  "stage_summaries": [
    {
      "stage_name": "input_normalization",
      "status": "failed",
      "started_at": null,
      "completed_at": null,
      "ref": null,
      "error_ref": "error-001"
    }
  ],
  "provider_turn_refs": [],
  "tool_result_refs": [],
  "memory_result_refs": [],
  "session_result_ref": null,
  "error": {
    "schema_version": "0.1.1-draft",
    "trace_id": "trace-003",
    "error_id": "error-001",
    "code": "VALIDATION_ERROR",
    "message": "Input event validation failed.",
    "recoverable": false,
    "source": "assistant_turn",
    "details": {}
  },
  "metadata": {}
}
```

## AssistantFinalResponse

Purpose: User-facing assistant response independent of provider response shape.

Fields:

- `schema_version`: string, required, non-empty.
- `response_type`: assistant-envelope enum, required. Allowed values: `text`, `error`, `payload_ref`.
- `text`: string or null, required, nullable.
- `payload_ref`: payload_ref object or null, required, nullable.
- `output_channel_intent`: assistant-envelope enum, required. Allowed values: `default`, `display`, `speech`, `both`.
- `safe_for_display`: boolean, required.
- `safe_for_speech`: boolean, required.
- `memory_write_candidate_hint`: boolean, required.
- `finish_reason`: assistant-envelope enum, required. Allowed values: `stop`, `length`, `cancelled`, `error`, `unknown`.
- `metadata`: object, required, may be empty.

Contract rules:

- `AssistantFinalResponse` may wrap the current `FinalResponse` conceptually, but must not become an alias for FinalResponse.
- Text-first behavior is supported without blocking future payload-ref output.
- TTS/UI details must not be provider-response fields.
- For `response_type=text`, `text` must be non-null and `payload_ref` must be null.
- For `response_type=payload_ref`, `payload_ref` must be non-null.
- For `response_type=error`, `text` must contain user-safe error text.
- Non-error responses require at least one content carrier.
- `output_channel_intent` is intent only, not dispatch.
- OutputRuntime owns actual dispatch later.
- `safe_for_display` means eligible for display, not required to display.
- `safe_for_speech` means eligible for speech, not required to speak.
- `memory_write_candidate_hint` is a candidate hint only.
- `memory_write_candidate_hint` is not memory write approval.
- `memory_write_candidate_hint` cannot cause writeback without a future `MemoryWriteCandidate` and PolicyRuntime approval.

Example: text response:

```json
{
  "schema_version": "0.1.1-draft",
  "response_type": "text",
  "text": "Hello.",
  "payload_ref": null,
  "output_channel_intent": "default",
  "safe_for_display": true,
  "safe_for_speech": true,
  "memory_write_candidate_hint": false,
  "finish_reason": "stop",
  "metadata": {}
}
```

Example: error response:

```json
{
  "schema_version": "0.1.1-draft",
  "response_type": "error",
  "text": "I could not complete that request.",
  "payload_ref": null,
  "output_channel_intent": "display",
  "safe_for_display": true,
  "safe_for_speech": false,
  "memory_write_candidate_hint": false,
  "finish_reason": "error",
  "metadata": {}
}
```

## Implementation Boundary

These four contracts are approved in `docs/CONTRACT_APPROVALS.md` for future
implementation.

This contract model implementation does not add runtime behavior.

Future runtime integration still requires a separate approved implementation task.

Forbidden outside a separate approved runtime task:

- Core orchestration changes using these contracts
- AssistantTurnRuntime implementation
- provider behavior changes
- CLI behavior changes
- service, HTTP, IPC, or worker runtime behavior
- memory, tools, voice, UI, desktop, or proactive behavior
