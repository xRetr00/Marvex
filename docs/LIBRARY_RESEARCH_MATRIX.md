# Library Research Matrix

## Purpose

This document persists the Task 045A ecosystem-wide library discovery posture.
Task 045A expanded discovery beyond the first shortlist from Task 045 and
confirmed that future Assistant OS subsystem work must not start from custom
infrastructure by default.

Marvex is library-first, adapter-isolated, contract-owned, and
framework-resistant. Future subsystem implementation requires a library decision record before custom code or new dependency.

## Current Approved Library Posture

The current approved provider-foundation posture remains unchanged:

- LiteLLM for provider adapter behavior.
- OpenAI SDK for LM Studio/OpenAI-compatible provider adapter behavior.
- Pydantic for contracts.

These approvals apply to the current provider foundation only. They do not
approve provider routing, fallback, assistant runtime behavior, memory, tools,
voice, desktop automation, persistent telemetry, or service runtime.

## Discovery Sources

Task 045A used broad ecosystem discovery sources, including:

- `vinta/awesome-python`
- `lukasmasuch/best-of-python`
- `Shubhamsaboo/awesome-llm-apps`
- an awesome agent-framework list
- an MCP ecosystem/source list
- official documentation and official GitHub repositories for serious
  candidates

Awesome-list inclusion is discovery evidence only. It is not approval.

## Ecosystem Matrix By Subsystem

| Subsystem | Research posture | Candidate families | Marvex boundary |
| --- | --- | --- | --- |
| local API/server runtime | Research before implementation | FastAPI / Litestar / possibly Connexion | ProcessRuntime/API adapter only |
| IPC / JSON-RPC / WebSocket / local auth | Research before implementation | WebSocket libraries, JSON-RPC libraries, Authlib | IPC adapter and ProcessRuntime boundary |
| provider routing/fallback | Separate future decision record | LiteLLM, OpenAI SDK, provider-native SDKs | ProviderRuntime selection only; no routing/fallback until approved |
| telemetry/logging/event persistence | Research before implementation | OpenTelemetry / structlog / CloudEvents / eventsourcing | Telemetry/EventRuntime adapters |
| memory runtime and vector/search backend | Research before implementation | mem0 / Letta, Qdrant local / LanceDB / Milvus Lite / SQLite FTS5 | MemoryRuntime contracts and adapters |
| MCP/tool execution/sandboxing | Research before implementation with security review | official MCP SDK/ecosystem, MCP server lists | ToolRuntime adapters under PolicyRuntime gates |
| process supervision and Windows service lifecycle | Research before implementation | psutil, APScheduler, watchfiles, Windows service options | ProcessRuntime adapters |
| config management | Research before implementation | Pydantic Settings / Dynaconf | config adapter, not Core |
| policy engine | Research before implementation | PyCasbin / Cedar / OPA | PolicyRuntime adapter |
| intent routing | Research before implementation | semantic routing, structured-output classifiers | IntentRuntime adapter |
| structured outputs/constrained generation | Research before implementation | OpenAI Structured Outputs / Instructor / Guardrails-style validation | provider-stage bridge adapter |
| voice STT/TTS | Research only; do not implement yet | OpenAI Audio / faster-whisper / Piper successor | VoiceRuntime/OutputRuntime adapter |
| desktop automation | Research only; do not implement yet | PyAutoGUI / Playwright / OS accessibility / MCP desktop servers | DesktopAgent adapter behind policy |
| agent observability/evals | Research before implementation | Phoenix / Braintrust / OpenTelemetry GenAI-style tooling | Telemetry/EventRuntime and test tooling adapters |

## Strong Future Decision Candidates

These are strong future decision candidates, not approved dependencies:

- FastAPI / Litestar / possibly Connexion for local API/server runtime.
- Authlib for local API/security research if local auth/OIDC/JWT becomes
  relevant.
- OpenTelemetry / structlog / CloudEvents / eventsourcing for telemetry, logs,
  and event persistence research.
- Qdrant local / LanceDB / Milvus Lite / SQLite FTS5 for retrieval/search
  research.
- mem0 / Letta as memory research targets only behind Marvex MemoryRuntime
  contracts.
- official MCP SDK/ecosystem for ToolRuntime adapters, with security review.
- PyCasbin / Cedar / OPA as PolicyRuntime research candidates.
- Pydantic Settings / Dynaconf for config research.
- Phoenix / Braintrust / OpenTelemetry GenAI-style tooling for agent
  observability/evals.
- OpenAI Structured Outputs / Instructor / Guardrails-style validation for
  structured output research.
- OpenAI Audio / faster-whisper / Piper successor for future voice research.
- PyAutoGUI / Playwright / OS accessibility / MCP desktop servers for future
  DesktopAgent research.

## Adapter-Only / Pattern-Only Candidates

These may inform design or sit behind adapters. They must not define Marvex
runtime ownership, contracts, state, policy placement, or assistant turn flow:

- LangGraph
- Pydantic AI
- OpenAI Agents SDK
- Microsoft Agent Framework
- LlamaIndex Workflows
- Haystack
- CrewAI
- Agno
- smolagents
- mem0
- Letta
- MCP server lists

## Avoid As Central Runtime

These must not become the central Marvex runtime:

- LangGraph
- CrewAI
- Agno
- Microsoft Agent Framework
- AutoGen
- OpenAI Agents SDK
- Pydantic AI
- LlamaIndex Workflows
- Haystack
- smolagents
- mem0
- Letta
- MCP SDK
- LiteLLM
- Phoenix/Braintrust

Reason: these may solve component problems, but must not own
AssistantTurnRuntime, Assistant Turn Spine, Core lifecycle, state model, memory
semantics, policy placement, provider routing, or tool exposure.

## Not Relevant Or Rejected Candidates

- Random MCP servers from ecosystem lists are not trusted by inclusion.
- Tutorial and app repositories from awesome lists are examples, not
  architecture dependencies.
- Annoy is not a primary memory store.
- FAISS is not a full assistant memory or event store.
- Supervisor is not suitable as the primary Windows process supervisor.
- AutoGen is not a new central framework candidate.
- Piper's original repository is not enough for final TTS approval because the
  successor project must be verified before use.

## Risk Matrix Summary

| Candidate family | Main risk |
| --- | --- |
| FastAPI / Litestar | service runtime shape leaking into Core |
| JSON-RPC / WebSocket libraries | protocol shape leaking into contracts |
| LiteLLM | provider routing/fallback expanding ProviderRuntime |
| OpenAI SDK | provider-native contract-shape leakage |
| OpenAI Agents SDK | framework takeover and tool exposure |
| LangGraph / CrewAI / Agno / Microsoft Agent Framework | central runtime takeover |
| Pydantic AI | assistant runtime and output contract leakage |
| mem0 / Letta | memory semantics takeover |
| MCP SDK/ecosystem | tool exposure and permission bypass risk |
| PyCasbin / Cedar / OPA | policy model leakage into unrelated runtimes |
| OpenTelemetry / structlog | diagnostic traces confused with assistant history |
| Phoenix/Braintrust | observability confused with memory or event history |
| OpenAI Audio / faster-whisper / Piper successor | voice worker coupling to provider completion |
| PyAutoGUI / Playwright / desktop MCP servers | desktop automation without policy and permission gates |

## Gaps Requiring Deeper Research

Future tasks must perform deeper subsystem-specific research for:

- JSON-RPC, WebSocket, MCP transport, and local auth.
- Tool execution security, sandboxing, allowlisting, audit records, and
  permission prompts.
- Desktop automation on Windows, including capture, accessibility APIs, and
  policy gates.
- Memory semantics across mem0, Letta, Zep-style memory, Haystack, LlamaIndex,
  and local storage.
- Persistent event storage separate from diagnostic trace logs and memory.
- Policy engine fit for `PolicyDecision` and `PermissionRequest` contracts.
- ProcessRuntime supervision, worker crash handling, cancellation, and Windows
  service lifecycle.
- Agent observability/evals across Phoenix, Braintrust, OpenTelemetry GenAI,
  OpenInference, and related tooling.
- Voice worker choices for STT, TTS, turn detection, streaming, and playback.
- Framework pattern extraction from agent frameworks without framework takeover.

## Required Future Library Decision Records

Library decision records are required before implementation for:

- local API/server runtime
- IPC / JSON-RPC / WebSocket / local auth
- provider routing/fallback
- telemetry/logging/event persistence
- memory runtime and vector/search backend
- MCP/tool execution/sandboxing
- process supervision and Windows service lifecycle
- config management
- policy engine
- intent routing
- structured outputs/constrained generation
- voice STT/TTS
- desktop automation
- agent observability/evals

Each decision record must follow `docs/LIBRARY_POLICY.md` and include official
source, maintenance status, why use it, why not custom code, fallback if
abandoned, pyproject dependency, and declared dependency.

Custom code is allowed only for:

- translating Marvex contracts into adapter calls
- runtime factory wiring after approval
- trace/cancellation propagation glue
- local policy/config object assembly
- error envelope normalization
- test fakes and deterministic fixtures

This glue must not become a custom SDK, hidden framework, custom provider
gateway, memory framework, tool framework, or event store.

## No Framework Takeover Rule

No framework or library may own Core or AssistantTurnRuntime.

No framework or library may own Assistant Turn Spine, memory semantics, policy
placement, tool exposure, provider routing, service lifecycle, or assistant
state model.

All accepted libraries must stay behind ports/adapters/runtimes. Core and
AssistantTurnRuntime remain Marvex-owned.
