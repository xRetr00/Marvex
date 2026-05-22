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

### Original V1 Baseline

The original V1 baseline included only:

- Core Service
- CLI Client
- Fake Provider
- LM Studio Responses Provider
- Telemetry

The original V1 baseline forbade:

- Intent
- Tools
- Memory
- UI
- Voice
- Desktop Context
- Proactive behavior
- Vision

These were the initial boundaries at V1. The current repository contains bounded foundations for several of them, each classified in `docs/GOVERNANCE_CLASSIFICATION.md`. Bounded foundations may be maintained and tested inside their current ownership boundaries but are not product permission and may not expand without explicit goal approval.

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
Core helper / AssistantRuntime provider-stage path. It is not wired into
services, APIs, default behavior, routing, sessions, retry/fallback, model
selection, API-key policy, tools, or memory.

Task 114 implementation note: CLI now has an explicit non-default
`--assistant-runtime-lmstudio-responses` proof mode that calls the
RuntimeComposition LM Studio Responses bridge. CLI still does not import
ProviderRuntime or adapters and does not own provider routing, retry/fallback,
session/history, model-selection, API-key, service/API, or product behavior.

Task 130 decision note: the next safest real-provider local API step is a
separate developer-only LM Studio Responses `/v1/turns` mode using explicit
`execution_mode: "assistant_runtime_lmstudio_responses"` and explicit request
`model`. It must be implemented, if approved, through RuntimeComposition
handler injection and the existing Core/AssistantRuntime provider-stage path.
Local API remains HTTP/auth/JSON only. Generic provider routing, model
selection, preflight enforcement, sessions/history, retry/fallback, API-key
policy, service daemon behavior, persistent traces, and WebSocket/events remain
blocked.

Task 133 decision note: LM Studio local API token configuration belongs to the
provider adapter construction path, not to Local API, Core, AssistantRuntime, or
request metadata. The current `LMStudioResponsesProviderConfig` has a
placeholder SDK key and `ProviderRuntimeConfig` has no credential field. The
next implementation should add a narrow LM Studio-only ProviderRuntime config
input that is converted into `LMStudioResponsesProviderConfig(api_key=...)`.
RuntimeComposition may pass that config for the developer-only LM Studio local
API runner, sourced from an environment variable value or explicit test fake,
but it must not own provider credential policy. `provider_options`, Local API
request bodies, `AssistantTurnInput.metadata`, traces, logs, and error
envelopes must not carry provider tokens.

Task 134 implementation note: ProviderRuntime now exposes the LM Studio-only
`lmstudio_responses_api_key` field and maps it only to
`LMStudioResponsesProviderConfig(api_key=...)`. The developer-only LM Studio
local API runner reads `MARVEX_LMSTUDIO_API_KEY` and passes it through
RuntimeComposition to ProviderRuntime without changing Local API request
envelopes, Core, AssistantRuntime, telemetry, provider routing, model selection,
preflight, retry/fallback, sessions/history, or default CLI behavior.

Task 137 decision note: future Marvex local service lifecycle and local bearer
token startup behavior belong to a future service runner/startup boundary. That
boundary may generate the local bearer token, keep startup/shutdown explicit,
and publish local-user-scoped discovery metadata or require explicit
CLI-provided config. It must not print the token value by default. Local API
remains only HTTP/auth/JSON, RuntimeComposition remains only approved
composition, ProviderRuntime remains provider construction, Core and
AssistantRuntime remain provider/service-lifecycle agnostic, and telemetry owns
trace safety. This decision does not implement a daemon, token generation,
token storage, discovery file, WebSocket/event stream, persistent telemetry,
sessions/history, routing, retry/fallback, model selection, or generic provider
mode.

Task 138 implementation note: `packages/local_service_startup` is that first
startup foundation boundary. It is not Local API, RuntimeComposition,
ProviderRuntime, Core, AssistantRuntime, or telemetry. It owns local bearer-token
generation and safe startup metadata only. Core, ProviderRuntime, Local API, and
RuntimeComposition do not import it yet; a future service-runner integration
task must explicitly approve any connection.

Task 117 implementation note: `packages/local_api` adds a dependency-free
local WSGI app object for `GET /health` and `GET /version` only, backed by the
approved `HealthCheck` and `VersionInfo` contracts. It defaults local API config
to `127.0.0.1`, adds no HTTP framework dependency, does not start a service
listener, and does not implement `/v1/turns`, provider execution,
RuntimeComposition assistant bridges, sessions/history, WebSocket, trace API,
tools, memory, or product behavior.

Task 118 implementation note: `packages.local_api.runner` adds a manual
standard-library loopback runner for the health/version app object. It is
developer smoke only, defaults to `127.0.0.1:8765`, and still does not implement
`/v1/turns`, provider execution, RuntimeComposition assistant bridges, Core or
AssistantRuntime turn execution, service daemon management, WebSocket, trace
API, sessions/history, tools, memory, or product behavior.

Task 119 implementation note: `packages.local_api.auth_policy` defines the
future protected local API auth-token helper without wiring it to health/version
or adding protected endpoints. Health/version remain public loopback readiness
endpoints. Future turn, trace, and event endpoints must use
`Authorization: Bearer <local-token>` and return safe `AUTH_REQUIRED`
`ErrorEnvelope` failures without logging or echoing token values.

Task 120 decision note: future `POST /v1/turns` is a protected local API
adapter endpoint, not a Core or RuntimeComposition-owned HTTP surface. The first
implementation target is fake-provider only, using a request envelope that
carries approved `AssistantTurnInput` and returns `AssistantTurnResult` when the
injected handler completes. `packages.local_api` owns only auth, JSON
validation, and serialization; RuntimeComposition owns provider/Core/
AssistantRuntime composition behind the injected handler. The API package must
not import RuntimeComposition, Core, AssistantRuntime, ProviderRuntime, adapters,
CLI apps, services, or provider SDKs. LM Studio Responses over `/v1/turns`,
trace APIs, event streams, service daemon behavior, sessions/history,
routing/retry/fallback, model-selection policy, API-key policy, tools, memory,
UI, voice, desktop, vision, and proactive behavior remain blocked.

Task 121 implementation note: `packages.local_api` now implements only the
protected `/v1/turns` HTTP/auth/JSON adapter with an injected
`LocalTurnRequestEnvelope -> AssistantTurnResult` handler. The API still does
not import or call RuntimeComposition, Core, AssistantRuntime, ProviderRuntime,
adapters, services, CLI apps, or provider SDKs.

Task 122 implementation note: RuntimeComposition now owns
`create_local_api_fake_turn_handler(...)`, the first fake-provider-only handler
factory for local API turn execution. The handler adapts the Task 121 envelope
to `run_fake_provider_assistant_bridge(...)`; local API receives it only by
injection and still does not import RuntimeComposition.

Task 123 implementation note: developer-only fake `/v1/turns` manual smoke is
owned by `packages.runtime_composition.local_api_fake_turns_runner`. That module
injects the RuntimeComposition fake handler into the local API runner with a
caller-provided fake/dev token. `packages.local_api` still does not import
RuntimeComposition.

Task 126 decision note: future `GET /v1/traces/{trace_id}` should be decided
and implemented before any real-provider `/v1/turns` API mode, but the first
strategy is current-process and in-memory only. `packages.telemetry` owns trace
recording, lookup, and read-time safety; `packages.local_api` may only expose an
injected trace reader through bearer-protected HTTP/auth/JSON; RuntimeComposition
must not own trace storage, trace lookup, or sanitizer policy. The endpoint must
return a local API envelope with sanitized trace-event projections, not raw
trace objects. Persistent telemetry, trace streaming, cross-process lookup,
service daemon lifecycle, sessions/history, and real-provider API execution
remain blocked until separate tasks approve them.

## Decision Runtime Boundary

Decision runtime owns decision pipeline wiring and execution helpers. CLI and
Core must not import the legacy decision-pipeline adapter directly for diagnostic behavior; live turn decisions are owned by CognitionRuntime and Core routing.
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

## Current Bounded Foundation Reality

The original V1 scope remains useful as a safety baseline, but the repository now contains several bounded internal foundations beyond the first provider slice. These foundations are classified in `docs/GOVERNANCE_CLASSIFICATION.md`.

Bounded foundations are not product approval. They may be tested and refactored inside their current ownership boundaries, but expansion requires the current goal spec, `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and relevant architecture docs to agree.

Current high-risk boundaries:

- CapabilityRuntime owns permission, approval, execution request validation, result envelopes, context delivery, and loop guards. It must not import Core, adapters, Local API, ProviderRuntime, Telemetry, MemoryRuntime, SessionRuntime, or RuntimeComposition.
- Assistant turn integration composes approved runtime layers. It must not become the assistant brain, provider router, memory policy owner, prompt policy owner, tool policy owner, or adapter execution owner.
- Local API and Control Plane own HTTP/auth/JSON and safe projections only.
- RuntimeComposition composes explicit approved paths only and must not become a router or policy engine.
- Core remains orchestration-only and must not absorb tools, memory, marketplace, Control Plane, browser/computer-use, voice, desktop, shell/orb, proactive behavior, or vision.

Existing code is not approval.
