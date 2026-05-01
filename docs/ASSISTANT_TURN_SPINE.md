# Assistant Turn Spine

## Purpose

This document prevents the current provider foundation from becoming the final
assistant architecture by accident.

Marvex is an Assistant OS / Agentic Runtime project. It is not an MVP,
prototype, provider-chat wrapper, or CLI-first assistant.

## Non-Negotiable Rule

The provider turn is not the assistant turn.

The provider path is only a foundation/test path.

Future intent, tools, memory, voice, desktop, policy, UI, proactive behavior,
and service runtime work require an approved Assistant Turn Spine and approved
contracts before implementation.

## Provider Turn vs Assistant Turn

Current provider turn:

```text
CLI input
-> TurnInput
-> ProviderRequest
-> ProviderResponse
-> FinalResponse
-> CLI output
```

This is allowed only as provider foundation behavior.

Future assistant turn:

```text
Input Event
-> Session / Identity / State Load
-> Intent / Goal Understanding
-> Initial Policy / Permission Check
-> Context Plan
-> Memory Retrieval under policy
-> Tool Plan under policy
-> Provider Reasoning
-> Tool Execution Loop with per-action policy gates
-> Final Response Assembly
-> Output Event / UI / TTS Handoff
-> Memory Writeback Candidate
-> Memory Write Policy Check
-> Telemetry / Persistent Event Commit
```

The assistant turn may call a provider zero, one, or many times. A provider call
is a stage inside the assistant turn, not the assistant turn itself.

## Target Assistant Turn Spine

The future control path must sit above provider calls:

```text
Client / Shell / CLI
-> InputEvent
-> Assistant turn boundary
-> Assistant runtime stage dispatch
-> session, intent, policy, context, memory, tool, provider, output, telemetry runtimes
-> AssistantTurnResult
```

Core may coordinate lifecycle, trace propagation, stage order, cancellation,
error envelopes, and final result assembly. Core must not own provider
protocols, memory storage, tool execution, desktop capture, speech, UI rendering,
or library-specific behavior.

## Stage Ownership Principles

- CLI is a client boundary. It must not own intent, memory, tools, policy,
  sessions, provider behavior, voice, UI, desktop context, or proactive behavior.
- Core owns assistant turn lifecycle coordination only. It must not become a
  giant assistant object.
- Runtime layers own selection, dispatch, lifecycle, and composition.
- Ports are minimal contracts only.
- Adapters own external protocols and library-specific code.
- ProviderRuntime owns provider creation only. It must not own routing,
  fallback, retry, session, history, service, tool, memory, or policy behavior.
- Context planning may plan memory and tool blocks, but it must not retrieve
  memory or expose tools by itself.
- Policy checks must happen before sensitive context exposure, memory reads,
  tool planning, each tool call, output exposure, and memory writeback.
- Every stage and worker boundary must propagate `trace_id`.

## Required Contract Families Before Implementation

These contract families must be designed and approved before their modules are
implemented:

- `InputEvent`
- `SessionState` / `ConversationState`
- `UserIdentity` / local profile boundary
- `IntentResult` / `GoalFrame`
- `PolicyDecision` / `PermissionRequest`
- `ContextPlan`
- `MemoryQuery` / `MemoryResult` / `MemoryWriteCandidate`
- `ToolCall` / `ToolResult` / `ToolPlan`
- `AssistantTurnPlan` / `AssistantTurnResult`
- `UIEvent` / `SpeechOutput` / `VoiceInput`
- `WorkerEnvelope` / `ServiceLifecycle`
- persistent trace/event records

Existing provider foundation contracts are not enough to implement assistant
modules. `TurnInput`, `TurnOutput`, `ProviderRequest`, `ProviderResponse`, and
`FinalResponse` remain provider-foundation contracts until an approved assistant
turn contract replaces or wraps them.

## Library Research Zones

Before custom implementation, future tasks must research maintained libraries,
SDKs, or repositories for:

- local API/server
- IPC, JSON-RPC, and WebSocket
- provider gateway behavior
- telemetry, structured logging, log/event storage
- memory systems
- vector/search storage
- config management
- process supervision
- tool execution and MCP
- agent/runtime framework patterns
- structured output

Any accepted library must remain behind ports/adapters. Core must stay clean and
replaceable.

## Anti-Vaxil Guardrails

- The provider turn is not the assistant turn.
- Intent must not be patched above the prompt/provider flow.
- Tools must not be patched above intent/provider flow.
- Memory must not be hidden inside ContextBuilder, ProviderRuntime, provider
  options, or prompt metadata.
- Policy must not be scattered across router, context, tools, providers, and CLI.
- Voice/TTS must not be coupled directly to provider completion.
- Desktop agent must not inject raw context into prompts without context planning
  and policy.
- TurnOrchestrator must not become a giant assistant god object.
- ProviderRuntime must not become routing, fallback, retry, session, or history
  logic.
- CLI must not become the main assistant runtime.
- Tool discovery must not mean tool exposure.
- Provider output must not directly write memory.

## Dangerous Next Work

These remain blocked until the Assistant Turn Spine and required contracts are
approved:

- tool execution
- memory storage, retrieval, or writeback
- voice or UI behavior
- desktop agent capture or automation
- proactive behavior
- persistent telemetry/event history
- HTTP, IPC, WebSocket, service runtime, or subprocess supervisor implementation
- provider routing, fallback, retry, or session history
- expanding TurnOrchestrator into assistant-level logic
- adding CLI assistant features beyond foundation/test path behavior

## Future Task Gate

Before any future implementation task, the task spec must answer:

1. Where does this work fit in the Assistant Turn Spine?
2. Which contract owns its input?
3. Which contract owns its output?
4. Is that contract approved for implementation?
5. Which runtime owns dispatch, selection, lifecycle, or composition?
6. Which port is the minimal boundary?
7. Which adapter owns external library/protocol code?
8. Which maintained library, SDK, or repository was considered before custom code?
9. If custom code is proposed, why is no maintained option suitable?
10. How does this avoid turning provider turn into assistant turn?
11. How does this avoid growing TurnOrchestrator into a god object?
12. How does this avoid expanding ProviderRuntime into routing/fallback/session/history logic?
13. How does this preserve future process separation?
14. How is trace_id propagated?
15. Where are policy checks enforced?
16. What is explicitly forbidden for this task?
