# Assistant Turn Envelope

## Purpose

This document records the smallest safe assistant-level turn envelope contract
direction above the current provider foundation.

The current provider path remains provider foundation only:

```text
CLI -> TurnInput -> ProviderRequest -> ProviderResponse -> FinalResponse -> TurnOutput
```

The smallest assistant-level envelope is:

- `InputEvent`
- `AssistantTurnInput`
- `AssistantTurnResult`
- `AssistantFinalResponse`

These are planning-level contract families. This document does not implement
Pydantic models, approve contracts, or change runtime behavior.

## Direct Rule

The provider turn is not the assistant turn.

The provider path is only a foundation/test path.

`TurnInput`, `TurnOutput`, and `FinalResponse` must not be silently repurposed as assistant-turn contracts.

Provider contracts remain provider-foundation scoped. Assistant-level contracts
must wrap or reference provider-foundation contracts, not mutate them into
assistant contracts.

TurnInput, TurnOutput, and FinalResponse must not be silently repurposed as assistant-turn contracts.

assistant-level contracts must wrap or reference provider-foundation contracts, not mutate them into assistant contracts.

## Current Provider Foundation Boundary

Current approved provider-foundation contracts:

- `TurnInput`
- `TurnOutput`
- `FinalResponse`
- `ProviderRequest`
- `ProviderResponse`
- `TraceEvent`
- `ErrorEnvelope`

`TurnInput` carries provider-foundation input such as `input_text`,
`previous_response_id`, `source`, trace id, turn id, and metadata. It does not
define normalized input events, modality, identity, session state, policy seed,
or assistant runtime entry.

`TurnOutput` carries the current provider-foundation result. It does not define
assistant stage summaries, output events, memory/tool/session references, or
assistant event history.

`FinalResponse` is the current user-facing response created from provider output
or provider error. It is not the future assistant response authority.

`ProviderRequest` and `ProviderResponse` are provider-only bridge contracts.
They must not carry assistant session state, tool results, memory data, desktop
context, voice/TTS fields, UI state, or policy decisions.

`TraceEvent` and `ErrorEnvelope` may remain shared base contracts, but
`TraceEvent` is diagnostic and is not persistent assistant history.

## Rejected Option: Reuse Provider Turn Contracts

Reusing `TurnInput` / `TurnOutput` / `FinalResponse` as assistant-turn contracts
is rejected.

It would:

- silently convert provider foundation into assistant runtime shape
- encourage assistant state inside `metadata`
- force future memory, tool, session, voice, UI, and desktop fields into the
  wrong contracts
- increase migration cost later
- violate the Assistant Turn Spine and Assistant Turn Contract Map

## Accepted Option: New Assistant Envelope Above Provider Foundation

Marvex should add a new assistant-level envelope above provider foundation when
the contracts are separately drafted and approved:

```text
InputEvent
-> AssistantTurnInput
-> AssistantTurnRuntime when approved
-> AssistantTurnResult
-> AssistantFinalResponse / output events
```

Provider calls may occur inside the assistant turn, but a provider call is a
stage inside the assistant turn. A provider call is not the assistant turn.

## Planned Contract Responsibilities

`InputEvent`

Normalizes external input from CLI, future Shell, Voice, Desktop, and proactive triggers before assistant turn entry.

Planning categories may include schema version, trace id, event id, source type,
input modality, payload body or payload reference, session reference, local
privacy/security metadata, timestamp, and metadata.

`AssistantTurnInput`

Assistant-level turn entry after input normalization. It is the future boundary
that Core may accept or hand into `AssistantTurnRuntime` after approval.

Planning categories may include schema version, trace id, turn id, input event
reference, session reference, identity/profile reference, user-visible input,
assistant mode/context flags, policy context seed, and metadata.

`AssistantTurnResult`

Complete assistant-level turn result, independent of whether provider calls happened.

Planning categories may include schema version, trace id, turn id,
assistant final response, output events, stage summaries, provider turn
references if used, tool/memory/session result references if later used, error
envelope, and metadata.

`AssistantFinalResponse`

User-facing assistant response independent of provider response shape.

Planning categories may include text or multimodal payload reference, response
type, safety/display/speech flags, output channel intent, memory writeback
eligibility hint, finish reason, and metadata.

These are not final schemas.

## Relationship To Existing Provider Contracts

`AssistantTurnInput` may wrap or reference `TurnInput` only for provider-only compatibility.

`AssistantTurnInput` must not become an alias for `TurnInput`.

`AssistantTurnResult` may reference provider `TurnOutput` or provider-stage summaries.

`AssistantTurnResult` must not be shaped around `provider_response_id`.

`AssistantFinalResponse` may initially wrap current `FinalResponse`, but
assistant response owns the user-facing result.

`ProviderRequest` and `ProviderResponse` remain provider-only.

`TraceEvent` and `ErrorEnvelope` may remain shared base contracts.

`TraceEvent` remains diagnostic unless persistent assistant event/history contracts are separately approved.

AssistantTurnInput may wrap or reference TurnInput only for provider-only compatibility.

AssistantTurnInput must not become an alias for TurnInput.

AssistantTurnResult may reference provider TurnOutput or provider-stage summaries.

AssistantTurnResult must not be shaped around provider_response_id.

AssistantFinalResponse may initially wrap current FinalResponse.

ProviderRequest and ProviderResponse remain provider-only.

TraceEvent and ErrorEnvelope may remain shared base contracts.

TraceEvent remains diagnostic unless persistent assistant event/history contracts are separately approved.

## Minimum Approval Path

Before implementation:

- Draft the assistant envelope contract docs.
- Add approval rows only as draft with `implementation_allowed: no`.
- Keep provider-foundation approval rows unchanged.
- Decide schema version handling before active references are introduced.
- Add migration notes explaining that provider contracts are wrapped or
  referenced, not repurposed.
- Add compatibility tests later proving provider foundation behavior remains
  stable.
- Add validation that blocks assistant fields from being smuggled through
  metadata escape hatches.

No assistant envelope contract may be used for implementation until
`docs/CONTRACT_APPROVALS.md` lists it as `approved` with
`implementation_allowed: yes`.

## Runtime Ownership Implications

Core owns the assistant lifecycle envelope after these contracts are approved.
Core owns top-level trace id, top-level cancellation, top-level error handoff,
and final `AssistantTurnResult` handoff.

`AssistantTurnRuntime` owns assistant stage dispatch after it receives
`AssistantTurnInput`.

`ProviderRuntime` remains provider-only and must not own session, history,
routing, fallback, memory, tools, context, or policy.

`OutputRuntime` later owns output-channel dispatch from assistant output
contracts when approved.

`Telemetry/EventRuntime` owns diagnostic trace emission and future event
persistence when approved.

CLI/Shell remain clients. They do not own assistant runtime behavior or
assistant turn history.

## Anti-Vaxil Contract Guardrails

- no assistant state hidden in `TurnInput.metadata`
- no memory/tool/session data hidden in `ProviderRequest.provider_options`
- no output-channel/TTS state hidden in `ProviderResponse.raw_metadata`
- no assistant history hidden in CLI args
- no persistent assistant history stored as raw `TraceEvent.data`
- no `AssistantTurnResult` replaced by provider `TurnOutput`
- no `InputEvent` used as an unnormalized raw UI, voice, desktop, or proactive
  blob
- no memory writeback eligibility inferred directly from provider output
- no policy decisions embedded in provider or router metadata
- no desktop context injected directly into provider input

Plain gate rules:

- no assistant state hidden in TurnInput.metadata
- no memory/tool/session data hidden in ProviderRequest.provider_options
- no output-channel/TTS state hidden in ProviderResponse.raw_metadata
- no persistent assistant history stored as raw TraceEvent.data

## Open Questions Before Schema Drafting

- Are `InputEvent` and `AssistantTurnInput` both required in the first draft?
- Should `InputEvent` be source-first, modality-first, or trigger-first?
- What is the minimum session reference shape before `SessionState` exists?
- Is identity represented as `UserIdentity`, `LocalProfile`, or a neutral
  reference first?
- Should `AssistantFinalResponse` be text-first initially or channel-first from
  the start?
- How should `OutputEvent` relate to `AssistantFinalResponse` without
  implementing UI or voice?
- Are diagnostic trace ids and persistent assistant event ids separate from the
  first draft?
- Should provider-only compatibility reference `TurnInput` / `TurnOutput` by id,
  embedded snapshot, or stage summary?
- Which current provider tests become compatibility tests once assistant
  contracts exist?
