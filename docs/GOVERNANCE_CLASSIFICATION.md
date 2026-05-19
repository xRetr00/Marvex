# Governance Classification

Existing code is not approval. Future work is allowed only when supported by the current goal spec, docs/CONTRACT_APPROVALS.md, PROJECT_STATUS.md, validation gates, and relevant architecture docs.

This registry classifies existing and future Marvex surfaces so green tests cannot silently convert bounded foundations into product permission.

## Classification Labels

- approved implementation surface: implementation is accepted for the explicitly described scope.
- bounded foundation: implementation exists, but expansion is policy-controlled or requires explicit goal approval for new behavior.
- experimental seam: adapter or proof code exists for evaluation and must not become product behavior.
- future service contract: draft/no implementation permission.
- policy-controlled: normal assistant capability controlled by AutonomyPolicy mode/matrix and audit records.
- hard-blocked blacklist only: malware, credential theft/extraction, data exfiltration, prompt-injection exploitation, command-injection exploitation, CAPTCHA/anti-bot bypass, stealth abuse, unauthorized account access, illegal destructive abuse, and payment/checkout without explicit enabled policy and approval path.
- forbidden product behavior for now: must not be implemented or enabled in product paths.

## Surface Registry

| surface | classification | owner boundary | expansion state |
| --- | --- | --- | --- |
| provider foundation | approved implementation surface | Core plus ProviderPort plus ProviderRuntime/adapters | Provider-foundation turns and explicit proofs only; no generic provider routing or model selection. |
| assistant turn contracts | approved implementation surface | contracts package and approved assistant-envelope docs | Only approved envelope models are implementation-approved; broader assistant contracts require explicit approval. |
| assistant turn integration | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.assistant_turn_integration | Validated integration spine only; must stay composition glue and not become assistant brain. |
| telemetry | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.telemetry | Safe trace events, local persistence, search summaries, and redaction only; no raw prompt/provider/tool payload storage. |
| local api | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.local_api | HTTP/auth/JSON adapter only; no direct runtime policy or tool/provider execution. |
| control plane api | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.control_plane_api | Protected safe projections and approval APIs only; no policy ownership or direct execution. |
| control plane web | bounded foundation: implementation exists, but expansion is blocked without explicit approval | apps/control_plane_web | Local admin dashboard only; no direct Python imports, secrets, or direct tool execution. |
| capability runtime | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.capability_runtime | Policy, permissions, approvals, eligibility, execution requests, result envelopes, and loop guards only. |
| tool execution foundations | bounded foundation: implementation exists, but expansion is blocked without explicit approval | CapabilityRuntime plus approved adapters | Safe built-ins and approved adapter requests only; no shell or filesystem write/delete tools. |
| mcp adapter/seam | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.adapters.capabilities.mcp | Official MCP SDK mechanics behind allowlist only; no arbitrary server launch, registry install, or auto-call. |
| browser/computer-use adapter/seam | experimental seam: not product-approved | packages.adapters.capabilities.browser and related seams | Playwright/browser/computer proposals remain policy-gated; risky actions require approval and remain bounded. |
| memory runtime | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.memory_runtime | Safe memory refs and SQLiteMemoryStore backend only; no raw transcript persistence by default. |
| OpenHuman-Style Memory Tree and Connectors Foundation | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.memory_tree_runtime and packages.connector_runtime | Source-grounded memory tree, connector/OAuth metadata, and auto-fetch policy foundation only; no hidden sync, raw token exposure, broad account actions, or copied OpenHuman code. |
| marketplace runtime | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.marketplace_runtime | Read-only metadata, validation, and enablement proposals only; no arbitrary install or execution. |
| session runtime | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.session_runtime | Safe session/conversation refs only; no hidden transcript store or global history. |
| intent/prompt harness seams | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.intent_runtime, packages.context_runtime, packages.prompt_harness_runtime | Intent/context/prompt plans from safe projections only; no all-tools/all-memory prompt dumping. |
| hybrid intent, web search, grounded evidence, and risk governance | bounded foundation: implementation exists, but expansion is blocked without explicit approval | packages.intent_runtime, packages.web_search_runtime, packages.grounded_answer_runtime, packages.capability_runtime | Safe read/list/search and public web grounding are allowed by default; write/delete/send/execute/risky actions require approval; abuse categories hard-block. No arbitrary tool execution, browser side effects, account access, raw payload persistence, or Voice runtime. |
| adaptive context, semantic memory search, learning, and granular governance | bounded foundation: implementation exists, but expansion is policy-controlled or requires explicit goal approval for new behavior | packages.prompt_harness_runtime, packages.memory_tree_runtime, packages.learning_runtime, packages.capability_runtime | Evidence/memory/tool/skill blocks are route-adaptive and safe-projection only; learning creates reviewable candidates only; governance decisions are audited and reason-coded. No Voice runtime or raw payload persistence. |
| autonomy modes and runtime policy control plane | policy-controlled | packages.capability_runtime.autonomy and Control Plane API/web | Locked Down, Ask Before Risky, Auto Marvex, and Custom modes expose a capability permission matrix. Read/list/search/web/page-read/MCP-list/memory-search are allowed by default. Side effects, sync, auto-fetch, memory/profile writes, skills, MCP execute, browser/computer actions, file operations, retry/fallback, and learning mutation candidates are allow/ask/deny/quarantine policy decisions with audit records. Hard-block is hard-blocked blacklist only. |
| runtime completion and phase unlock | approved implementation surface | IntentRuntime, ContextRuntime, PromptHarnessRuntime, CapabilityRuntime, ProviderSelectionRuntime, ConnectorRuntime, LearningRuntime, Control Plane | Grounded answer flow, adaptive prompt/context injection, multi-candidate planning, dynamic tool selection, per-request risk policy, provider selection/fallback, turn recovery, learning feedback/apply flow, connector sync/auto-fetch runner, and policy-controlled MCP/shell/file seams are implemented before Voice. Shell/file execution adapters, direct Browser-use task execution, and real external OAuth account sync remain not implemented adapters or credential-dependent paths, not broad governance hard-blocks. |
| voice runtime foundation | bounded foundation: implementation exists, but expansion is policy-controlled or requires explicit goal approval for new behavior | packages.voice_runtime plus Control Plane API/web voice views | VoiceRuntime owns voice I/O orchestration, backend selection, wakeword/VAD/audio buffering, streaming speech chunking, barge-in state, early speech/personality policy, safe voice turn envelopes, asset registries, and safe Control Plane projections. It must not own intent routing, tools, memory, provider routing, capability policy, autonomy policy, visual UI, hidden recording, or raw audio/transcript persistence by default. |
| service placeholders | future service contract: draft/no implementation permission | services/* README-only placeholders | README-only until matching service contract is approved for implementation. |
| future voice worker/service process | future service contract: draft/no implementation permission | future voice worker service | The in-process VoiceRuntime foundation is approved, but separate always-running worker processes, OS microphone capture services, daemon supervision, and product voice shell behavior still require a future explicit service contract. |
| future desktop agent | forbidden product behavior for now | future desktop agent | No desktop control, OS automation, credential extraction, or overlay behavior. |
| future shell/orb ui | forbidden product behavior for now | future shell/orb UI | No Orb, desktop overlay, final assistant shell, or native UI runtime. |
| future proactive behavior | forbidden product behavior for now | future proactive worker | No autonomous/proactive behavior or background assistant actions. |
| future vision | forbidden product behavior for now | future vision worker | No vision/screen understanding product path. |

## Hard Rule

Existing code is not approval. Normal assistant capabilities must be implemented, policy-controlled, not implemented, proof-only, or hard-blocked blacklist only. A future goal must update this registry, docs/CONTRACT_APPROVALS.md, PROJECT_STATUS.md, validation gates, and relevant architecture docs before expanding any bounded foundation into product behavior.
