# Governance Classification

Existing code is not approval. Contract approval and contract status live only in `docs/CONTRACT_APPROVALS.md`.

This registry describes where each Marvex surface sits in the architecture so green tests cannot silently turn a scoped surface into product behavior.

## Classification Labels

- documented surface: implementation exists and is described here.
- bounded foundation: implementation exists and stays inside its owner boundary.
- evaluation seam: adapter or proof code exists for evaluation.
- draft service contract: a service folder exists as a placeholder and remains README-only.
- policy-controlled surface: normal assistant capability controlled by AutonomyPolicy mode/matrix and audit records.
- safety-restricted surface: the surface stays limited to safe projections and explicit allowlists.
- future product surface: the surface is not part of current product behavior.

## Surface Registry

| surface | classification | owner boundary | notes |
| --- | --- | --- | --- |
| provider foundation | documented surface | ProviderPort plus ProviderRuntime/adapters plus ProviderWorker service boundary | ProviderRuntime is the adapter factory/runtime foundation. ProviderWorker owns local provider execution, selection, fallback/retry execution, timeout/unavailable classification, and safe process envelopes. Contract status lives in `docs/CONTRACT_APPROVALS.md`. |
| assistant turn contracts | documented surface | contracts package and assistant-envelope docs | Assistant-level contract planning lives in `docs/ASSISTANT_TURN_CONTRACT_MAP.md`; status lives in `docs/CONTRACT_APPROVALS.md`. |
| assistant turn integration | bounded foundation | packages.assistant_turn_integration | Validated integration spine only. |
| telemetry | bounded foundation | packages.telemetry | Safe trace events, local persistence, search summaries, and redaction only. |
| local api | bounded foundation | packages.local_api | HTTP/auth/JSON adapter only. |
| control plane api | bounded foundation | packages.control_plane_api | Protected safe projections and approval APIs only. |
| control plane web | bounded foundation | apps/control_plane_web | Local admin dashboard only. |
| capability runtime | bounded foundation | packages.capability_runtime | Policy, permissions, approvals, eligibility, execution requests, result envelopes, and loop guards only. |
| tool execution foundations | bounded foundation | CapabilityRuntime plus approved adapters | Safe built-ins and approved adapter requests only. |
| intent worker process | documented surface | services/intent_worker wrapping packages.intent_runtime | Local JSONL classification process only; safe projections, backend name, health/version/status, no providers, no approvals, no tool execution, and no raw input persistence by default. |
| tool worker process | documented surface | services/tool_worker wrapping packages.capability_runtime | Local JSONL capability execution process only; existing AutonomyPolicy checks, safe fake/status capability proof, structured blocked results, no provider calls, and no raw argument/output persistence by default. |
| mcp adapter/seam | bounded foundation | packages.adapters.capabilities.mcp | Official MCP SDK mechanics behind allowlist only. |
| browser/computer-use adapter/seam | evaluation seam | packages.adapters.capabilities.browser and related seams | Playwright/browser/computer proposals remain policy-gated. |
| memory runtime | bounded foundation | packages.memory_runtime | Safe memory refs and SQLiteMemoryStore backend only. |
| OpenHuman-Style Memory Tree and Connectors Foundation | bounded foundation | packages.memory_tree_runtime and packages.connector_runtime | Source-grounded memory tree, connector/OAuth metadata, and auto-fetch policy foundation only. |
| marketplace runtime | bounded foundation | packages.marketplace_runtime | Read-only metadata, validation, and enablement proposals only. |
| session runtime | bounded foundation | packages.session_runtime | Safe session/conversation refs only. |
| intent/prompt harness seams | bounded foundation | packages.intent_runtime, packages.context_runtime, packages.prompt_harness_runtime | Intent/context/prompt plans from safe projections only. |
| hybrid intent, web search, grounded evidence, and risk governance | bounded foundation | packages.intent_runtime, packages.web_search_runtime, packages.grounded_answer_runtime, packages.capability_runtime | Safe read/list/search and public web grounding are allowed by default; write/delete/send/execute/risky actions still require explicit policy decisions. |
| adaptive context, semantic memory search, learning, and granular governance | policy-controlled surface | packages.prompt_harness_runtime, packages.memory_tree_runtime, packages.learning_runtime, packages.capability_runtime | Evidence/memory/tool/skill blocks are route-adaptive and safe-projection only. |
| autonomy modes and runtime policy control plane | policy-controlled surface | packages.capability_runtime.autonomy and Control Plane API/web | Locked Down, Ask Before Risky, Auto Marvex, and Custom modes expose a capability permission matrix. |
| runtime completion and phase unlock | documented surface | IntentRuntime, ContextRuntime, PromptHarnessRuntime, CapabilityRuntime, ProviderSelectionRuntime, ConnectorRuntime, LearningRuntime, Control Plane | Grounded answer flow, adaptive prompt/context injection, multi-candidate planning, dynamic tool selection, per-request risk policy, provider selection/fallback, turn recovery, learning feedback/apply flow, connector sync/auto-fetch runner, and policy-controlled MCP/shell/file seams are implemented before Voice. |
| cognition runtime | bounded foundation | packages.cognition_runtime | Pure turn assembly only: intent projection, context, memory/web evidence refs, prompt plan, and bounded step plan. No providers, worker internals, subprocesses, or raw persistence. |
| bounded agentic turn loop | documented surface | services/core/main.py composing packages.cognition_runtime and worker IPC | Core-owned bounded Agentic Turn Loop with grounding enforcement, safe tool execution, approval pause/resume, and trace projection. This does not authorize arbitrary tools, hidden autonomy, desktop/browser/computer execution, raw payload persistence, or production daemon behavior. |
| core service entrypoint | documented surface | services/core/main.py plus packages.core service foundation | Minimal local runnable Core service boundary: loopback Local API startup, health/version one-shot, provider selection flags, ProviderWorker process roundtrip proof, protected turn path, and clean shutdown. No remote bind, daemon supervisor, hidden autostart, or raw prompt/provider-output persistence. |
| provider worker service | documented surface | services/provider_worker/main.py plus services/provider_worker controller/models | Local JSONL process boundary for provider execution through ProviderRuntime. Owns provider selection, retry/fallback execution, timeout/unavailable classification, safe command/result envelopes, health/version, and shutdown. No memory, tools, desktop, UI, voice, proactive behavior, streaming, production supervision, or remote mode. |
| voice runtime foundation | bounded foundation | packages.voice_runtime plus Control Plane API/web voice views | VoiceRuntime owns voice I/O orchestration, backend selection, wakeword/VAD/audio buffering, streaming speech chunking, barge-in state, early speech/personality policy, safe voice turn envelopes, asset registries, and safe Control Plane projections. |
| voice worker runtime | documented surface | packages.voice_worker_runtime, services/voice_worker README, protected Control Plane worker projections | Local-only worker implementation surface; contract status lives in `docs/CONTRACT_APPROVALS.md`. |
| shell product surface | documented surface | apps/shell Tauri shell | Approved Windows tray supervisor and product UI host. It starts and owns local backend child processes, renders chat/control, status pill/waveform, and Spotlight approvals as a loopback client only. It does not own provider/intent/tool/voice/cognition/memory/policy logic, does not persist raw payloads or tokens, and does not authorize desktop agent, vision, or proactive behavior. |
| service placeholders | draft service contract | services/* README-only placeholders except approved services/core, services/provider_worker, services/intent_worker, and services/tool_worker entrypoint files | README-only until the matching contract is listed in `docs/CONTRACT_APPROVALS.md` and a service-owned entrypoint task exists. Contract approval alone does not authorize implementation. |
| future memory service | future product surface | future memory service boundary | Reserved for a future service boundary only; current memory behavior remains in `packages.memory_runtime` and related bounded foundations. |
| future telemetry event service | future product surface | future telemetry event service boundary | Reserved for a future service boundary only; raw event persistence and projection rules remain telemetry-owned and policy controlled. |
| future policy/permission service | future product surface | future policy/permission service boundary | Reserved for a future service boundary only; policy truth remains in `packages.capability_runtime` and AutonomyPolicy governance, not in an approved implementation path here. |
| future voice product behavior | future product surface | future voice shell/orb/desktop surfaces | VoiceWorker does not imply Orb, Face UI, desktop overlay, final visual assistant shell, vision, proactive behavior, hidden recording, or remote worker exposure. |
| future desktop agent | future product surface | future desktop agent | No desktop control, OS automation, credential extraction, or overlay behavior. |
| future orb ui | future product surface | future Orb UI | No Orb product behavior. The approved Shell surface uses a Siri-style waveform overlay only. |
| future proactive behavior | future product surface | future proactive worker | No autonomous/proactive behavior or background assistant actions. |
| future vision | future product surface | future vision worker | No vision/screen understanding product path. |

## Hard Rule

Existing code is not approval. Every other doc should refer back to `docs/CONTRACT_APPROVALS.md` for contract status and use this registry only for scope and ownership.
