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

## Provider Architecture Path

`Core -> ProviderPort -> ProviderRuntime/Factory -> LiteLLMAdapter / LMStudioResponsesAdapter / FakeProvider`

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
