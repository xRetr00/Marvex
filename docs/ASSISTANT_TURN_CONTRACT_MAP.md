# Assistant Turn Contract Map

## Purpose

This document records the contract map required before Marvex can implement
Assistant OS / Agentic Runtime behavior.

Current approved contracts are provider-foundation contracts, not assistant-turn contracts.
They support the provider foundation path only:

```text
CLI -> TurnInput -> ProviderRequest -> ProviderResponse -> FinalResponse
```

## Direct Rule

The provider turn is not the assistant turn.

`TurnInput`, `TurnOutput`, `ProviderRequest`, `ProviderResponse`, and
`FinalResponse` must not be silently repurposed as full assistant-turn contracts.

Assistant-level modules require Assistant Turn Spine alignment, approved
contracts, runtime ownership clarity, and library research where relevant.

## Existing Provider Foundation Contracts

Approved provider-foundation contracts:

- `TurnInput`
- `TurnOutput`
- `FinalResponse`
- `ProviderRequest`
- `ProviderResponse`
- `TraceEvent`
- `ErrorEnvelope`
- `HealthCheck`
- `VersionInfo`

These contracts remain valid for provider foundation, process-readiness object
construction, and current validation. They are not permission to implement
intent, tools, memory, voice, UI, desktop agent, proactive behavior, service
runtime, worker IPC, persistent telemetry, or assistant runtime behavior.

## Required Assistant-Level Contract Families

The following are missing or insufficient until separately drafted and approved:

- `InputEvent`
- `AssistantTurnInput`
- `AssistantTurnPlan`
- `AssistantTurnResult`
- `SessionState` / `ConversationState`
- `UserIdentity` / `LocalProfile`
- `IntentResult` / `GoalFrame`
- `PolicyDecision` / `PermissionRequest`
- `ContextPlan`
- `MemoryQuery`
- `MemoryResult`
- `MemoryWriteCandidate`
- `MemoryWriteResult`
- `ToolPlan`
- `ToolCall`
- `ToolResult`
- `ReasoningRequest` or provider-stage bridge
- `AssistantFinalResponse`
- `OutputEvent`
- `SpeechOutput`
- `UIEvent`
- `VoiceInput`
- `WorkerEnvelope`
- `ServiceLifecycle`
- `PersistentTraceRecord`
- `AssistantEventRecord`

Existing draft shapes such as `IntentDecision`, `PromptPlan`,
`DecisionPipelineResult`, and `TurnPreflightResult` are not enough to implement
assistant-level modules.

## Provider Foundation Relationship

Provider foundation contracts should be wrapped by assistant-level contracts, not
mutated into broad assistant contracts.

Future assistant contracts may translate an assistant reasoning stage into a
`ProviderRequest` and may wrap a `ProviderResponse` inside assistant turn output.
They must not add assistant session state, memory data, tool results, voice
fields, UI data, or policy shortcuts into provider contracts.

`TurnInput` and `TurnOutput` should remain provider-foundation contracts unless
a future approved migration explicitly changes their role with replay tests and
rollback rules.

## Minimum Contract Sets Before Future Modules

Before intent:

- `InputEvent` or `AssistantTurnInput`
- minimal `SessionState`
- `IntentResult` / `GoalFrame`
- policy handoff contract

Before memory:

- `UserIdentity` / `LocalProfile`
- `SessionState` / `ConversationState`
- `PermissionRequest` / `PolicyDecision`
- `ContextPlan`
- `MemoryQuery`
- `MemoryResult`
- `MemoryWriteCandidate`
- `MemoryWriteResult`

Before tools:

- `GoalFrame`
- `PermissionRequest` / `PolicyDecision`
- `ToolPlan`
- `ToolCall`
- `ToolResult`
- tool error and permission contracts

Before voice or UI:

- `InputEvent`
- `VoiceInput`
- `OutputEvent`
- `SpeechOutput`
- `UIEvent`
- session and trace ownership

Before desktop agent:

- desktop input/context event contract
- `UserIdentity` / `LocalProfile`
- `PermissionRequest` / `PolicyDecision`
- `ContextPlan`
- redaction and evidence contracts

Before service runtime or worker IPC:

- `WorkerEnvelope`
- `ServiceLifecycle`
- service auth/session contract
- shutdown, cancellation, and error contracts

Before persistent telemetry:

- `PersistentTraceRecord`
- `AssistantEventRecord`
- retention, privacy, and access contracts

## Approval and Versioning Rules

- No assistant-level contract is implementation-approved until it has an
  approval row with `approval_status: approved` and `implementation_allowed: yes`.
- Existing provider-foundation approval rows remain unchanged.
- Service placeholder contracts remain draft/blocker until explicitly approved.
- Breaking contract changes require schema version review, migration notes,
  rollback notes, and replay tests.
- Unknown assistant shapes must not be smuggled through `metadata`,
  `provider_options`, `raw_metadata`, `details`, or `TraceEvent.data`.

## Library Research Hooks

Contracts must stay library-neutral, but future implementation tasks must
research maintained libraries before custom code:

- memory: mem0 or alternatives, vector stores, SQLite/FTS, retention behavior
- tools: MCP SDK, native tool adapters, sandboxing, permission scopes
- event history: event stores, structured logging, replay/history systems
- IPC: FastAPI, WebSocket, JSON-RPC, local auth and transport patterns
- service lifecycle: process supervision and service discovery options
- structured output: Pydantic, provider-native structured output, Outlines, or
  Pydantic-AI patterns where appropriate
- voice: maintained STT/TTS wrappers before custom audio infrastructure
- config: maintained configuration libraries before custom config systems

Accepted libraries must remain behind ports/adapters.

## Anti-Vaxil Contract Guardrails

- No memory hidden in `provider_options`, `raw_metadata`, prompt metadata, or `TraceEvent.data`.
- No tool result hidden inside prompt text or provider response text.
- No policy decision embedded as a side effect of router output.
- No desktop context injected directly into `ProviderRequest`.
- No voice/TTS fields inside `ProviderResponse` or provider adapter metadata.
- No session history inside `ProviderRuntime`.
- No assistant turn state inside CLI arguments beyond client input.
- No unstructured JSON blobs outside approved metadata fields.
- No assistant-level fields added to provider contracts as shortcuts.
- No memory writeback from provider output without `MemoryWriteCandidate` and policy approval.
- No persistent event/history storage using plain trace logs without an approved event record.

## Open Questions Before Schema Drafting

- Should the top-level assistant entry contract be `InputEvent`,
  `AssistantTurnInput`, or both?
- Should `TurnInput` and `TurnOutput` remain permanently provider-foundation
  contracts or be deprecated after assistant contracts exist?
- Does Core own assistant stage sequencing, or does a separate assistant runtime
  own dispatch?
- What is the first approved session model?
- What policy scopes are required before tools, memory, desktop, and voice?
- Is assistant history event-sourced, memory-backed, or both?
- Are diagnostic traces and assistant event history separate stores?
- Which worker envelope and transport shape is approved for service runtime?
