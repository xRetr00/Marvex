# Runtime Ownership

## Purpose

This document records runtime ownership boundaries for the future Assistant Turn
Spine. It prevents Core, AssistantTurnRuntime, ProviderRuntime, ContextBuilder,
CLI/Shell, ports, or adapters from becoming god objects.

The current provider path remains provider foundation only:

```text
CLI -> TurnInput -> ProviderRequest -> ProviderResponse -> FinalResponse
```

The provider turn is not the assistant turn.

## Accepted Ownership Decision

Core owns the assistant lifecycle envelope.

AssistantTurnRuntime owns assistant stage dispatch.

Subsystem runtimes own domain selection, dispatch, lifecycle, and execution.

Adapters own external protocols and library-specific code.

Ports remain minimal contracts only.

## Core Boundary

Core owns:

- assistant lifecycle envelope
- top-level trace id
- top-level cancellation signal
- top-level error envelope handling
- final AssistantTurnResult handoff when approved

Core must not own assistant stage internals.

Core must not own:

- provider selection
- intent routing
- policy engine internals
- memory backend selection
- tool dispatch
- UI/TTS routing
- desktop capture
- process supervision
- external protocol/library code

## AssistantTurnRuntime Boundary

AssistantTurnRuntime owns:

- assistant stage dispatch
- stage order
- per-stage lifecycle coordination
- stage result aggregation
- one-turn assistant state snapshots and safe state projections
- trace/cancellation propagation to stages

Current implemented lifecycle foundation: `packages.assistant_runtime` owns safe
stage lifecycle primitives and projections for one turn. It records only safe
refs, counts, presence bits, stage statuses, and trace linkage readiness. It
does not perform subsystem dispatch, persistence, routing, retry/fallback,
memory extraction, or daemon supervision.

AssistantTurnRuntime must not own subsystem internals.

AssistantTurnRuntime must not own:

- provider SDK behavior
- session history or transcript storage
- memory storage
- tool execution internals
- policy engine internals
- UI rendering
- voice capture/TTS implementation
- telemetry storage engine
- process supervision

## Subsystem Runtime Boundaries

- SessionRuntime owns session/conversation state lifecycle.
- IntentRuntime owns intent/goal routing and validation composition.
- PolicyRuntime owns permission and policy decisions.
- ContextRuntime owns context planning only.
- MemoryRuntime owns memory query/write dispatch and backend selection.
- ToolRuntime owns tool planning, selection, dispatch, and execution lifecycle.
- ProviderRuntime owns provider adapter selection/creation only.
- OutputRuntime owns output channel dispatch.
- Telemetry/EventRuntime owns trace/event emission, persistence, replay/query surfaces when approved.
- ProcessRuntime owns service lifecycle, health/version, startup/shutdown/supervision when approved.

Each subsystem runtime must use approved contracts and must remain replaceable.
Library-specific behavior belongs in adapters.

## Dispatch and Selection Ownership

- Provider selection belongs to ProviderRuntime.
- Intent route selection belongs to IntentRuntime.
- Policy engine selection belongs to PolicyRuntime.
- Context block selection belongs to ContextRuntime.
- Memory backend selection belongs to MemoryRuntime.
- Tool selection and tool execution dispatch belong to ToolRuntime.
- Output channel dispatch belongs to OutputRuntime.
- Telemetry sink/event-store selection belongs to Telemetry/EventRuntime.
- Worker process dispatch belongs to ProcessRuntime.
- Retry/fallback policy belongs to an explicitly approved runtime/policy owner, not Core by default.
- Timeout policy must be explicit and enforced by the responsible runtime.

No port may contain dispatch, selection, registry, factory, retry, or lifecycle behavior.

## Failure and Cancellation Ownership

Core owns the top-level cancellation signal and top-level unrecovered error
handoff.

AssistantTurnRuntime propagates cancellation to active stages and aggregates
stage failures.

Subsystem runtimes convert local subsystem failures into approved error
contracts and decide local cleanup behavior.

ProcessRuntime owns worker crash detection and service lifecycle failures when
approved.

Telemetry/EventRuntime owns telemetry write failure reporting and must not
silently swallow persistence failures.

## Trace and Event Ownership

Core creates or accepts the top-level `trace_id`.

AssistantTurnRuntime propagates `trace_id` to every stage.

Subsystem runtimes propagate `trace_id` to adapters and future workers.

Provider calls receive `trace_id` through provider contracts.

Future worker calls receive `trace_id` through approved worker envelopes.

Telemetry/EventRuntime owns diagnostic trace emission and future event
persistence. Diagnostic trace events are not memory records. Assistant
event/history records are not raw telemetry logs.

AssistantRuntime state projections link to telemetry by `trace_id` and `turn_id`
only. They may expose presence flags, reference counts, stage statuses, and
sanitized transition reasons, but not raw prompts, provider payloads, provider
outputs, tokens, transcripts, or session bodies. `previous_response_id` remains
explicit caller input and may be represented only as presence/absence in
AssistantRuntime state snapshots.

SessionRuntime owns safe `session_ref` and `conversation_ref` linkage for turn
grouping. It may project `trace_id`, `turn_id`, safe references,
`previous_response_id` presence, and `transcript_persisted: false`; it must not
store raw transcripts, raw prompts, provider payloads, provider outputs, tokens,
provider response ids, or long-term recall data. Core, Local API,
RuntimeComposition, ProviderRuntime, telemetry, and local service startup may
carry or link safe references only through approved contracts and must not become
session lifecycle owners.

MemoryRuntime owns memory records, memory refs, memory write candidates, safe
read results, safe forget results, and future memory read/write orchestration.
It may link records to `session_ref`, `conversation_ref`, `trace_id`, and
`turn_id`, but it must not store raw transcripts by default or delegate memory
ownership to Core, Local API, RuntimeComposition, telemetry, ProviderRuntime,
AssistantRuntime, SessionRuntime, or local service startup.

## Anti-God-Object Guardrails

- `TurnOrchestrator` must not be expanded into assistant-level logic.
- Core must not become a giant assistant orchestrator.
- AssistantTurnRuntime must not become a policy/memory/tool/provider god object.
- ProviderRuntime must not own sessions, history, fallback policy, tools, memory, context, or policy.
- ContextRuntime / ContextBuilder must not retrieve memory, expose tools, decide policy, or call providers.
- Policy decisions must not be scattered across router/context/tool/provider/CLI code.
- Telemetry/EventRuntime must not become memory or session history.
- CLI/Shell must remain clients and must not own assistant runtime behavior.
- Ports must not contain dispatch, selection, registry, factory, retry, or lifecycle behavior.
- Adapters must not own product orchestration.

## Dangerous Runtime Work

These remain blocked until runtime ownership, contracts, and library research are
approved:

- implementing AssistantTurnRuntime
- expanding `TurnOrchestrator`
- adding runtime packages for memory, tools, voice, UI, desktop, proactive behavior, or service runtime
- adding provider routing, fallback, retry, or session history to ProviderRuntime
- adding memory/tool/policy behavior to ContextBuilder
- adding assistant runtime behavior to CLI/Shell
- implementing HTTP, IPC, WebSocket, subprocess supervisor, or service daemon
- implementing telemetry persistence or assistant event history
- adding dependencies before library decision records

## Future Runtime Task Gate

Before any runtime-related implementation task, the task spec must answer:

1. Which runtime owns this work?
2. Is that runtime already approved for implementation?
3. Which contract owns the runtime input?
4. Which contract owns the runtime output?
5. Which layer owns dispatch?
6. Which layer owns selection?
7. Which layer owns lifecycle?
8. Which layer owns failure/cancellation behavior?
9. How is trace_id propagated?
10. Which policy checkpoints apply?
11. Which maintained library/SDK/repo was considered before custom code?
12. How does this avoid expanding Core into a god object?
13. How does this avoid expanding AssistantTurnRuntime into subsystem internals?
14. How does this avoid expanding ProviderRuntime into routing/session/history/fallback?
15. How does this avoid putting memory/tool/policy behavior into ContextBuilder?
16. What is explicitly forbidden for this task?

## Open Questions Before Runtime Implementation

- Where should AssistantTurnRuntime live if approved?
- What is the first approved AssistantTurnRuntime input/output contract?
- What is the cancellation contract shape?
- Which runtime owns timeout policy configuration?
- Which failures are degradable by default?
- What is the boundary between diagnostic trace events and assistant event history?
- Which process supervision library or pattern will be approved?
- Does provider fallback require a separate provider routing runtime?

## CapabilityRuntime Boundary

CapabilityRuntime owns manifests, eligibility decisions, permission decisions, human approval requirements, context delivery policy, compaction policy, provider/tool-call proposal envelopes, permission-gated execution requests, result/error envelopes, safe summaries, loop guards, planning readiness models, and verification hooks.

Capability adapters own external protocol integration only. MCP, OpenAI tool, LiteLLM gateway, LM Studio, skill, plugin, connector, and integration adapters cannot bypass CapabilityRuntime policy. Core, ProviderRuntime, RuntimeComposition, Local API, MemoryRuntime, SessionRuntime, Telemetry, and local_service_startup must not become capability registries, dispatchers, or execution owners.
