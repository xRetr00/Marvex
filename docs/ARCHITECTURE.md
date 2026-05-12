# Architecture

## Executive Decision

Marvex is a hybrid, service-ready desktop system.

The first implementation target is:

- Python Core Service
- CLI Client
- Fake Provider
- LM Studio Responses Provider
- Telemetry

The later desktop target is:

- C++/Qt Shell
- Python Core Service
- Provider Worker
- Tool Worker
- Intent Worker
- Voice Worker
- Desktop Agent

This is not immediate microservices. It is a modular core designed so each major boundary can become a separate process without rewriting the product.

## V1 Scope

V1 includes only:

- Core Service
- CLI Client
- Fake Provider
- LM Studio Responses Provider
- Telemetry

V1 forbids:

- Intent
- Tools
- Memory
- UI
- Voice
- Desktop Context
- Proactive behavior
- Vision

These future modules may be documented, but they may not be implemented in v1.

## Core Principle

The Core Service owns turn orchestration only. It does not own provider-specific logic, UI behavior, tool execution, memory storage, voice capture, desktop observation, or policy decisions for modules that do not exist yet.

The Core talks through ports and stable JSON contracts.

The provider turn is not the assistant turn. The current provider path is only a
foundation/test path. Future assistant-level intent, tools, memory, voice,
desktop, policy, UI, proactive behavior, and service runtime work must follow
`docs/ASSISTANT_TURN_SPINE.md` and approved contracts before implementation.

Runtime ownership is explicit: Core owns the assistant lifecycle envelope,
AssistantTurnRuntime owns assistant stage dispatch, subsystem runtimes own domain
selection/dispatch/lifecycle/execution, adapters own external protocols, and
ports remain minimal contracts only.

## Service-Ready Modular Core

Every future module must be designed as if it may later run in a separate process:

- explicit input contract
- explicit output contract
- health check
- version field
- structured logs
- trace_id propagation
- error envelope
- startup and shutdown behavior

If a module cannot be separated without rewriting the Core, the module boundary is wrong.

## Provider Boundary

The Core sends `ProviderRequest` to a Provider Adapter through a port. The Core must not know whether the backend is LM Studio, OpenAI-compatible, local, remote, fake, or replaced later.

`previous_response_id` belongs in the provider contract and adapter behavior, not in hidden Core state.

## Port Contract Discipline

Ports are minimal contracts only. A port is not a manager, registry, router, implementation container, or runtime.

`ProviderPort` must remain tiny:

- It defines only provider interface methods and request/response contract types.
- It must not mention concrete provider names such as LiteLLM, LM Studio, OpenAI, OpenRouter, Anthropic, or Gemini.
- It must not contain provider selection, retry policy, API key handling, config loading, streaming logic, tool logic, history logic, or parsing logic.
- Concrete providers live under `packages/adapters/providers/<provider_name>/`.

Tool ports must remain tiny:

- `ToolExecutorPort` defines only `execute(ToolCall) -> ToolResult`.
- Tool ports must not contain built-in tool implementations.
- Built-in tools live under `packages/adapters/tools/<tool_family>/<tool_name>.py`.
- Tool selection, permission, and dispatch live in `tool_runtime/`, not in port files.

## Folder Boundary Guidance

- `packages/ports/` = interfaces only
- `packages/adapters/` = concrete implementations
- `runtime/` = factory, registry, dispatch, lifecycle
- `packages/core/` = orchestration using ports only
- `apps/` = clients only

## Frontend Boundary

Future web UI, Native Orb/Presence, trace/event viewer, settings, and
voice/face visualization surfaces are clients and presentation shells only.
They must not own backend/provider/runtime logic, provider selection,
`previous_response_id` behavior, retry policy, structured-output parsing, tool
execution, memory writes, desktop control, session truth, or policy decisions.

`docs/FRONTEND_BOUNDARY.md` is the authoritative planning document for frontend
ownership until approved HTTP/WebSocket contracts and separate implementation
task specs exist.

## Provider Architecture Path

`Core -> ProviderPort -> ProviderRuntime/Factory -> LiteLLMAdapter / LMStudioResponsesAdapter / FakeProvider`

## ProviderRuntime Production Bridge Ownership Decision

Decision title: ProviderRuntime Production Bridge Ownership After Task 109.

Current context: Tasks 105 through 109 prove an assistant-runtime provider-stage
path with a fake provider only. AssistantRuntime owns
`run_provider_stage_turn(...)`; Core owns the narrow
`run_assistant_provider_stage_turn(...)` helper; CLI exposes the explicit
`--assistant-runtime-fake-provider` foundation mode. No real ProviderRuntime
provider is wired into that assistant-runtime path.

Options considered:

- CLI-owned composition: fastest for a command, but wrong for service/API or
  desktop shell reuse. It would make CLI choose providers, build provider
  runtime objects, call Core, and format output, which risks a god client.
- Core-owned composition: rejected. Core owns turn orchestration, not provider
  selection or provider construction. Core must not import ProviderRuntime or
  adapters.
- AssistantRuntime-owned composition: rejected. AssistantRuntime owns
  assistant-stage behavior and must stay provider-runtime agnostic. It should
  accept an injected send-capable provider, not build one.
- ProviderRuntime-owned composition: rejected. ProviderRuntime owns provider
  construction/provider-facing behavior and must not import Core or
  AssistantRuntime.
- Separate runtime composition/factory layer: recommended. A future narrow
  production bridge layer should compose ProviderRuntime-created providers into
  the Core assistant-provider-stage helper without moving ownership into CLI,
  Core, AssistantRuntime, ProviderRuntime, ports, or adapters.

Recommended owner: a future separate runtime composition/factory layer. It may
be introduced only by a separate implementation task. Its responsibility should
be limited to production composition: accept approved assistant-turn input and
provider runtime config, ask ProviderRuntime for a send-capable provider, inject
that provider into Core's assistant-provider-stage helper, and return the
approved assistant result shape.

Dependency direction:

```text
CLI or future service/app surface
  -> future runtime composition/factory layer
    -> Core assistant-provider-stage helper
      -> AssistantRuntime provider-stage function
    -> ProviderRuntime provider factory
      -> Provider adapters
```

Allowed imports for the future bridge layer:

- approved contracts
- telemetry sink contract/event construction as needed
- `packages.provider_runtime` factory/config
- `packages.core.orchestration.assistant_provider_stage`

Forbidden imports for the future bridge layer:

- concrete provider adapters
- provider SDKs
- CLI apps
- services as implementation dependencies
- tools, memory, UI, voice, desktop, vision, proactive behavior
- session/history stores, retry/fallback routers, model routers, or API-key
  loaders unless separately approved

Explicit forbidden directions:

- Core must not import ProviderRuntime or adapters.
- AssistantRuntime must not import ProviderRuntime, Core, adapters, or ports.
- ProviderRuntime must not import Core or AssistantRuntime.
- CLI must not import concrete provider adapters or own production provider
  bridge policy.
- Ports must not become factories, registries, routers, or managers.

What this unlocks next: a bounded implementation task can add the separate
bridge/factory layer plus tests proving a ProviderRuntime-created fake provider
can be injected into the Core/AssistantRuntime assistant-provider-stage path
without changing default CLI behavior or real provider product behavior.

What remains blocked: real provider-backed AssistantRuntime product turns,
default CLI promotion, service/API behavior, telemetry persistence, sessions,
history, routing, retry/fallback, tools, memory, UI, voice, desktop, vision,
and structured-output public contract promotion.

Validation/gate implications: existing gates already block the most dangerous
directions for Core, AssistantRuntime, ProviderRuntime, ports, and CLI adapter
imports. A future bridge implementation must add a dedicated boundary gate for
the new bridge package so it can import only the approved composition targets
and cannot import adapters or own runtime policy.

Rollback path: if the separate bridge layer becomes too broad, delete or
deprecate that layer and return to explicit test-only composition. Core,
AssistantRuntime, ProviderRuntime, provider adapters, ports, and CLI default
behavior should remain unchanged by such a rollback.

Task 111 implementation note: `packages/runtime_composition` now contains the
first fake-provider-only proof of this ownership model. It creates the approved
`fake` provider through ProviderRuntime, injects it into the Core helper, and
relies on Core to reach AssistantRuntime provider-stage behavior. It is not
wired into default CLI behavior, services, APIs, real providers, sessions,
history, routing, retry/fallback, tools, or memory.

Task 112 implementation note: the official CLI
`--assistant-runtime-fake-provider` mode now calls the RuntimeComposition fake
bridge instead of constructing a local fake provider. CLI also delegates the
existing provider-foundation turn composition to RuntimeComposition so CLI no
longer imports ProviderRuntime directly. Default CLI output behavior remains
unchanged.

Task 113 implementation note: RuntimeComposition now has one explicit
real-provider-backed AssistantRuntime proof function for `lmstudio_responses`.
It obtains that provider through ProviderRuntime and injects it into the same
Core helper / AssistantRuntime provider-stage path. It is not wired into CLI,
services, APIs, default behavior, routing, sessions, retry/fallback, model
selection, API-key policy, tools, or memory.

## Decision Runtime Boundary

Decision runtime owns decision pipeline wiring and execution helpers. CLI and
Core must not import decision runtime modules directly for diagnostic behavior.
Decision factories are composition helpers only: no dev components, payload
shaping, routing behavior, validation behavior, policy behavior, or business
decisions.

## Tool Architecture Path

`Core -> ToolRegistryPort/ToolExecutorPort -> ToolRuntime/Dispatcher -> individual tool adapters`

## Anti-God-File Review Checks

- Any port contract file over 120 lines fails review unless explicitly justified.
- Any port contract file mentioning concrete implementation names fails review.
- Any adapter file importing Core fails review.
- Any Core file importing adapters fails review.
- Any registry or factory file over 250 lines requires split or explicit justification.

## Anti-Spaghetti Rules

- No god files.
- No giant orchestrator.
- No hidden global state.
- No provider-specific code in Core.
- No UI logic in Core.
- No tool execution in UI.
- No features before contracts.
- No custom SDKs when maintained libraries exist.
