# Project Status

current_phase: native_asgi_control_plane_state_boundary_checkpoint

implementation_status: native_asgi_control_plane_state_boundary_checkpoint

accepted_docs: true

current_governance_gate:
Native ASGI Control Plane State Boundary Checkpoint

## Native ASGI Control Plane State Boundary Checkpoint

Marvex has started the native-ASGI endpoint ownership migration. Core and
Control Plane still run under the Uvicorn two-port host, but Control Plane
`/control/state` and `/control/state/stream` are now owned by native ASGI routes
with the existing WSGI Control Plane app mounted as fallback for all other
routes. The state stream remains SSE, uses the same safe `AssistantStateEvent`
frame shape, keeps bearer and HttpOnly browser-session cookie auth behavior, and
unsubscribes from the state bus on stream close.

The migration plan for the remaining WSGI-to-ASGI phases is tracked in
`docs/NATIVE_ASGI_MIGRATION_PLAN.md`. Core `/v1/turns`, trace lookup,
Control Plane sessions, browser-session claims, static SPA serving, approvals,
voice controls, dependency installs, and other Control Plane APIs intentionally
remain on the compatibility bridge until their dedicated slices move them.

## Windows Shell Overhaul: Async Bridge, Presence, Control Plane Window, Always-On Voice Checkpoint

The Tauri Windows shell (`apps/shell`) was reworked for responsiveness, presence, persistence, and an always-on voice posture:

- Responsiveness: the shell's backend bridge is now async and non-blocking. The raw blocking `TcpStream` HTTP connector was replaced with async `reqwest`, and the networking Tauri commands (`submit_chat_turn`, `control_request`, `backend_health`) are `async`, so loopback I/O no longer runs on the main/UI thread. This fixes the whole-app freeze (chat, startup, and tray menu) and the overlay mousemove IPC flood (now edge-triggered) and idles the WebGL waveform GPU loop at rest.
- Presence ("soul"): the dynamic island overlay is anchored top-right, shows live assistant state at idle, and expands the waveform on hover. Spotlight is no longer a manually-summoned mode/window — it is a content-sized card spawned from the island on events (e.g. `needs_approval`); the dock button, tray item, and global shortcut were removed.
- Persistence: shell chat uses a durable local session store with a real `session_ref` (replacing the hardcoded `shell-session`); conversations restore on relaunch and prior sessions are listable/resumable. The chat hardcoded `fake-model` turn was dropped so Core uses its configured provider/model, and failure states (backend offline / no provider / provider error / empty) surface explicit, actionable messages instead of "No displayable response returned."
- Control Plane: the full original `control_plane_web` (Providers, Voice Runtime with model/voice/STT selection + downloads, Agents/Personas, etc.) opens in a dedicated Tauri window. The Control Plane server serves the SPA same-origin and authenticates the browser through a shell-requested one-time claim URL that sets an HttpOnly SameSite Control Plane cookie; the browser no longer receives or stores the raw local bearer token in `sessionStorage`. The shell's prior minimal in-shell Control Plane and Deps tabs were retired.
- Always-on voice: the "Hey Marvex" wake word is now enabled by default (`VoiceWorkerWakewordConfig.enabled = True`), intended to run 24/7 under a backend Windows service so Core stays warm for instant wake response. This overrides the earlier "disabled by default" posture below. Detection still requires the installed sherpa-onnx KWS asset; there is no hidden audio capture and the no-raw-audio/transcript/generated-audio persistence and safe-projection guarantees are unchanged. The wake-word/STT/TTS model assets must be shipped with the installer and the wake-word worker is a required (non-optional) build artifact.

Still host-dependent/manual at this checkpoint: bundling the actual model asset binaries (sources are operator-supplied), registering/running the backend as a Windows service, and the WebView2/audio/installer GUI smokes.

## Desktop Agent Computer-Use Proactive Checkpoint

DesktopAgent, computer-use, and Proactive surfaces are now approved in bounded form. DesktopAgent is a local-only perception worker that returns safe focused-window and screenpipe-recall projections only. Computer-use is opt-in and approval-required through ToolWorker/CapabilityRuntime. Proactive behavior is proposal-only, visible, local-only, and gated by learning preferences; it does not execute hidden background actions.

## Windows Shell Product Surface Checkpoint

Marvex now has an approved Shell contract for the Tauri v2 Windows shell under `apps/shell`. The shell is a product surface and local supervisor only: it generates an in-memory local bearer token, starts the approved Core and worker entrypoints as windowless child processes, exposes a tray-resident app with chat, a top-left state pill/waveform overlay, and a Spotlight/approval surface, and consumes loopback Core and Control Plane contracts. Chat session truth is backend-owned; shell localStorage is only a visible-message/UI cache keyed by backend session refs. The shell does not implement provider, intent, tool, voice, cognition, memory, policy, desktop-agent, vision, or proactive behavior.

The shell is additive to the Python backend. Core turn requests still go through `/v1/turns`, approvals still go through protected Control Plane approval APIs, and assistant/voice visual state is consumed from `/control/state` and `/control/state/stream` when those Control Plane endpoints are present. The waveform is bound to `AssistantStateEvent.audio_level`; no random waveform production is used for listening/talking states. Tokens are not persisted or logged by shell code.

Packaging support lives under `apps/shell/packaging` and `apps/shell/scripts` with PyInstaller specs for the local sidecar executables and Tauri bundler `externalBin` declarations for the Windows installer path. Operator GUI/audio/package smoke remains a local runtime smoke because it requires WebView2, Windows shell integration, physical audio state, and the packaged installer.

## Personal Cognitive Operating Layer Memory + Context Checkpoint

Marvex now has the first live Personal Cognitive Operating Layer slice. Core worker-backed turns can use an explicit local memory vault root, inject a real `session_ref`, recall approved derived memory through `SQLiteMemoryStore`, assemble the prompt with the actual user question plus bounded recalled memory content, and send persistent policy through the provider `instructions` channel instead of collapsing everything into one user blob.

`packages.cognition_runtime` now calls the adaptive prompt harness path (`adaptive_context_policy_for_route` and `assemble_adaptive_prompt_harness`) for live turn assembly. Memory context sections carry real bounded memory text and provenance refs, not tombstone placeholders. The compaction, tool-result-clearing, and memory-offload decision models are called during candidate assembly so budget pressure produces safe summaries without mid-subtask mutation.

`LocalMemoryLoop` writes only derived, policy-approved facts. It uses `AutonomyPolicy`/`memory_auto_write`, `MemoryWriteCandidate(source="future_policy")`, `MemoryPolicyDecision(decided_by="future_policy")`, `MemoryRecord(write_authorization="policy_approved")`, and the existing memory stores. Belief revision forgets the prior topic record before writing the replacement, so contradictory facts do not accumulate as duplicate current truth.

The local memory vault is an explicit configurable path (`--memory-vault-root`) and is ignored by git via `.marvex-memory/`. The vault projection writes Obsidian-compatible Markdown under `wiki/summaries/` and creates `wiki/notes/` for human-editable notes. Markdown frontmatter carries source/provenance fields and `raw_secret_persisted: false`; generated bodies use `[[wikilinks]]`. The local SQLite memory store and Memory Tree index live under the same explicit vault root. Raw transcripts, raw prompts, raw provider output, raw tool payloads, tokens, credentials, and secrets remain forbidden.

The developer-only `scripts/smoke_core_prompt_fidelity.py` proof runs the Core provider-worker path through the real `lmstudio_responses` adapter against a loopback Responses-compatible endpoint and captures the actual provider request structure. It proves the request has a system/instructions channel plus a user channel containing the real question, real recalled memory, and evidence-shaped memory context without requiring CI network access. A live external LM Studio/LiteLLM smoke remains host-dependent and manual.

Still future after this checkpoint: broad tool library, production agentmemory daemon, real external connector live sync at scale, larger automatic extraction coverage, Voice product loop, Orb/shell UI, desktop agent, proactive behavior, and production-grade hybrid retrieval beyond the local Markdown plus SQLite index.

## Intent and Tool Worker Execution Slice Checkpoint

Marvex now has a local end-to-end Intent + Tool/Capability execution slice across process boundaries. `services/intent_worker` is a runnable JSONL classification worker around `packages.intent_runtime.classify_intent`, exposes start/stop/status/health/version/classify, returns `SafeIntentProjection` plus backend metadata, clamps input through the runtime request model, and does not execute tools, approve actions, call providers, or persist raw input by default.

`services/tool_worker` is a runnable JSONL capability execution worker around `packages.capability_runtime`. It exposes start/stop/status/health/version/execute, evaluates the existing `AutonomyPolicy`/`AutonomyMode.AUTO_MARVEX` policy path, executes only the existing safe deterministic fake/status capability when policy allows, returns safe result/projection/audit records, and returns structured blocked results for unapproved side effects such as file delete/write without persisting raw arguments or output.

`services/core/main.py` now preflights provider-worker turns through the IntentWorker subprocess before deciding the route. Simple chat still flows through the existing ProviderWorker subprocess. Capability/tool intent flows through the ToolWorker subprocess. Clarification intent returns a clarification response. Unsafe or injection-suspected intent is blocked before provider/tool execution. Risky actions reach the ToolWorker policy path and are blocked without approval. Trace and turn IDs propagate across Core, IntentWorker, ToolWorker, and the structured Core result.

This checkpoint does not add a broad tool library, shell/file/browser/desktop execution adapters, memory writes, remote service mode, production daemon supervision, richer approval UX, proactive behavior, voice product loop, desktop agent, or shell/orb UI.

## Voice Worker Runtime Boundary Checkpoint

Marvex now has the first dedicated local voice worker boundary in `packages.voice_worker_runtime`. The worker layer owns explicit local lifecycle commands, heartbeat/status, loopback-only process launch, microphone and playback adapters, safe model asset root validation, worker events, and safe Control Plane projections. It is local-only, rejects remote process bindings, does not auto-start, and does not allow hidden recording or raw audio/transcript/generated-audio persistence by default.

The `VoiceWorker` service contract is listed in `docs/CONTRACT_APPROVALS.md` for the local-only worker implementation surface. That registry entry covers explicit worker lifecycle, safe command/status/event contracts, microphone capture and speaker playback adapters, model asset readiness/downloads under the safe asset root, backend runner adapters, wakeword supervision, and worker-safe telemetry. It does not imply Orb/shell UI, desktop agent behavior, vision, proactive behavior, remote worker exposure, hidden recording, or raw audio/transcript/generated-audio persistence by default.

The worker process path now starts in JSONL contract mode for persistent local supervision. A supervising service can launch the loopback-only worker subprocess, send `VoiceWorkerCommand` envelopes over stdin, and read safe `VoiceWorkerCommandResult` JSON lines over stdout. Command envelopes can carry an explicit `trace_id`, JSONL health/version commands roundtrip through the worker contract path, invalid commands return structured `VoiceWorkerErrorEnvelope` projections without echoing raw invalid input, and the safe cancellation command shape clears playback/queued TTS state without persistence. The process path is covered by both in-memory JSONL loop tests and a real subprocess roundtrip test. The process still rejects remote bindings, does not hidden-autostart, and exits on explicit `stop`.

`sounddevice==0.5.5` is declared as the local audio device dependency and isolated behind `SoundDeviceAudioAdapter`; tests use `FakeLocalAudioAdapter` because CI cannot validate physical microphone or speaker hardware. The worker can list/test fake devices, select devices through config reload, capture PCM frames without persistence, run a bounded live capture cycle with injected/mockable VAD decisions, pre-roll, silence cutoff, tail padding summaries, and max-utterance stop before assistant dispatch, run a manual voice turn through VAD/STT/policy/assistant/TTS/playback event stages, emit safe event-count telemetry summaries, and interrupt playback for barge-in. `VoiceWorkerBackendRuntime` now checks installed local assets plus package import/version availability and uses package-specific model adapters for Moonshine v2, SenseVoice-Small/FunASR, Kokoro-ONNX, and Piper only after readiness passes, while safe command summaries suppress raw transcripts and synthesis text. Non-persistent in-memory audio refs and generated-audio refs now support runner handoffs without rendering PCM bytes. Explicit local model downloads now copy `file://` assets or fetch HTTPS bytes into the safe voice asset root, validate optional checksums through the existing install path, and expose safe download status through the worker Control Plane endpoint. Real live heavy inference smoke against installed assets, package-specific sherpa-onnx KWS invocation, and physical device smoke remain explicit local/manual work.

Control Plane API/web now exposes protected voice worker status, start/stop/pause/resume, config reload, microphone and playback tests, device lists/selectors, wakeword/STT/TTS test commands, model install/download/remove, backend/model readiness, safe telemetry counts, backend switching, and active voice switching. Model asset handling now reports missing files as `not_installed`, checksum mismatches as `needs_attention`, and Hey Marvex wakeword tests as not-ready until wakeword is enabled and the sherpa-onnx KWS asset is installed. VoiceWorkerRuntime does not own AutonomyPolicy, CapabilityRuntime, assistant turn execution policy, RuntimeComposition supervision, or Local API internals.

## Voice Runtime Foundation Checkpoint

Marvex now has a bounded VoiceRuntime foundation after runtime completion and phase unlock. `packages.voice_runtime` owns voice I/O orchestration only: wakeword, VAD, audio ring buffers, chunk aggregation, STT/TTS backend selection, model/voice registries, sentence clamping, queued speech, barge-in state, early safe filler speech, voice personality settings, safe voice turn envelopes, and safe Control Plane projections.

Adopted voice dependencies are `moonshine-voice==0.0.59`, `funasr==1.3.1`, `sherpa-onnx==1.13.2`, `sherpa-onnx-core==1.13.2`, `kokoro-onnx==0.5.0`, `piper-tts==1.4.2`, `stream2sentence==0.3.2`, `silero-vad==6.2.1`, and `webrtcvad-wheels==2.0.14`. The uv compatibility probe resolved successfully; `uv run python -m pip check` initially found missing `sherpa-onnx-core`, and adding the explicit dependency fixed the check. VoiceRuntime now imports `silero_vad`, `webrtcvad`, and `stream2sentence` through concrete adapters for VAD and sentence boundaries, with safe fallback behavior when package execution fails on a host.

Control Plane API/web now exposes protected Voice Runtime status, STT/TTS backend selectors, active voice selection, voice/model download request surfaces, STT/TTS test actions, wakeword settings, VAD/barge-in/early speech/personality settings, audio retention policy, backend health, and telemetry summaries. Frontend voice controls call protected backend APIs and do not run audio engines directly.

Voice turns use injected assistant-turn and policy callbacks so VoiceRuntime does not own intent routing, tools, memory, provider routing, CapabilityRuntime, AutonomyPolicy, or visual UI. Prompt-injection-like transcripts can be quarantined before assistant execution; ambiguous voice commands ask clarification; risky actions produce voice approval prompts without execution. Wakeword 24/7 support is explicit, visible, policy-controlled, and disabled by default. Raw audio, generated audio, transcripts, backend internals, provider payloads, tool payloads, and secrets are not persisted or rendered by default.

Still not implemented after this checkpoint: Orb/Face UI, desktop overlay, final visual assistant shell, vision, proactive non-voice behavior, real external OAuth credential sync against user accounts, direct Browser-use SDK task execution, and actual shell/file execution adapters. These remain future explicit goals or policy-controlled/not-implemented seams.


## Phase History

Previous completed phases (these markers are retained for gate compatibility):

- `current_phase: adaptive_context_evidence_memory_learning_governance_complete`
- `implementation_status: adaptive_context_evidence_memory_learning_governance_complete`
- `governance_reconciliation_boundary_hardening_complete`

## uv Dependency Workflow Checkpoint

Marvex now has a `uv.lock` and a uv-backed dependency validation path. Dependency-changing work should use `uv lock`, `uv sync`, `uv run python -m pip check`, `uv run python -m pytest -q`, and `uv run python scripts/run_all_checks.py`; one-off pip upgrades remain outside the safe workflow.
## SDK Adoption Checkpoint

Marvex adopted `semantic-router==0.1.14` behind `packages.adapters.intent.semantic_router_adapter` for local, no-cloud route definition and scoring proof only. IntentRuntime remains the policy owner; Semantic Router cannot own execution, tools, memory, prompt assembly, or routing policy.

Marvex adopted `openai-agents==0.17.2` only as a compatibility dependency behind `packages.adapters.capabilities.openai_agents`. This required moving to `openai==2.37.0` and `litellm==1.85.0` after resolver proof. The OpenAI Agents SDK cannot own the Marvex agent loop, policy, tool dispatch, prompt harness, or runtime composition.

`guardrails-ai` is unavailable in the current Python 3.12.0 environment because pip found no matching distribution. The Guardrails adapter remains a tested safe-projection validation seam with an explicit unavailable backend reason; Guardrails cannot assemble prompts or run automatic retry loops.

`browser-use==0.11.13` is adopted as a main-environment dependency for import-backed adapter proof. Latest `browser-use==0.12.6` remains unavailable because it pins `openai==2.16.0`, conflicting with Marvex's OpenAI Agents-compatible `openai==2.37.0`. The browser-use backend remains disabled for execution, CapabilityRuntime policy remains mandatory, and Playwright `1.60.0` remains the low-level browser SDK path.

LlamaIndex and LangChain/LangGraph remain deferred. Resolver dry-runs succeeded, but both bring broad runtime/agent/context ownership surfaces that are not needed until a later context selector or planning backend phase.


## OpenHuman-Style Memory Tree and Connectors Foundation

Marvex now includes a bounded OpenHuman-style memory tree and account-awareness connector foundation. The implementation is conceptual only and does not copy OpenHuman code.

Implemented foundation surfaces:

- `packages.memory_tree_runtime` for canonical source documents, normalized Markdown, bounded chunks, content hashes, scoring, source/topic/global/daily tree nodes, evidence links, SQLite tree index, vault projection, and safe traversal/search.
- `packages.connector_runtime` for required connector manifests, OAuth connection metadata, read-only connector scopes, sync requests/results, error envelopes, and disabled-by-default auto-fetch policies.
- `packages.adapters.connectors.authlib_oauth` as the adopted `Authlib==1.7.2` OAuth seam with import proof only; no token exchange or sync starts by default.
- Control Plane API/web views for connectors, sources, auto-fetch, memory tree search, source/topic/daily tree browsing, evidence drill-down, scoring explanation, and source forget request summaries.

Auto-fetch is implemented as policy-controlled state with schedules and per-connector/per-source enablement, but defaults to disabled. Control Plane toggles expose state only and do not start hidden sync. OAuth tokens, credentials, raw account content, raw transcripts, raw provider payloads, and raw tool payloads remain out of safe projections and telemetry by default.

Nango, Airbyte CDK, Meltano/Singer, Pipedream, Markdown/frontmatter parsers remain reference/deferred unless a later backend-specific goal adopts one behind an adapter. Authlib is the only new runtime dependency for this checkpoint.

## Memory Tree Completion Audit Checkpoint

The memory tree follow-up audit closed in-boundary gaps without adding live connector sync. Evidence links now flow through safe tree projections, scoring projections include component explanations, SQLite tree index readbacks include evidence metadata, source forget deletes indexed documents/chunks/scores/tree nodes, and Control Plane web exposes source tree, topic tree, daily digest, evidence drill-down, source forget, and auto-fetch controls. Live OAuth sync, background schedules, and broad account actions were still future work at this checkpoint and are now represented by the later autonomy policy layer.

## Assistant Intelligence and Tool-Using Runtime Integration Checkpoint

Marvex now has a bounded deeper tool-using assistant turn path. IntentRuntime can use deterministic routing or an injected semantic-router-backed adapter result while still owning Marvex intent decisions. ContextRuntime and PromptHarnessRuntime select only route-relevant safe context, including Memory Tree evidence refs/counts for memory-tree-needed turns. Provider tool calls remain proposals; CapabilityRuntime remains the only owner of approval, execution requests, result envelopes, and dispatch policy. The integration includes the safe browser workflow, allowlisted MCP live proof path, approval resume/deny/cancel state, provider continuation readiness, trace-searchable safe telemetry summaries, and Control Plane-safe counts/status projections.

Checkpoint limitation: generic provider routing/model selection, retry/fallback behavior, direct browser-use execution, broad browser/computer actions, MCP server launch/install, shell/filesystem tools, live OAuth/account sync, auto-fetch, raw transcript/prompt/tool/provider/browser payload persistence, voice, Orb/Face UI, desktop overlay, and proactive behavior were not implemented or required later policy controls.


## Provider Tool Continuation and Live Execution Hardening Checkpoint

Marvex now has a bounded provider tool continuation path for safe built-in execution. LM Studio/OpenAI-compatible provider tool calls are normalized as proposals, malformed arguments are denied without fallback execution, safe calculator results become provider continuation input summaries, and final fake-provider continuation responses are represented without persisting raw provider payloads or raw tool arguments.

Approval resume now distinguishes allow, deny, and cancel outcomes in safe projections. Playwright-backed browser navigation can execute after CapabilityRuntime policy when a page boundary is supplied; click/type remain policy-gated and no browser-use execution was promoted. Trace search and Control Plane summaries expose only counts/status booleans for proposal, policy decision, execution, continuation, and final response state.

## Real Tool-Using Assistant Runtime Completion Checkpoint

Marvex now has a narrow real provider continuation handoff path: provider tool calls from OpenAI-compatible, LM Studio, or LiteLLM-shaped payloads map into Marvex-owned proposals, unsafe tool names are denied instead of normalized into executable actions, safe built-in execution remains CapabilityRuntime-owned, and an injected ProviderPort-compatible continuation adapter receives only safe continuation summaries before producing the final assistant response. The default no-provider test path remains an explicit fake-provider proof rather than generic provider routing.

Browser-use moved beyond import-only to a controlled adapter proof that exposes allowed browser-agent categories and the exact direct-execution blocker, while Playwright remains the real low-level SDK-backed browser path. Control Plane now exposes a Runtime Execution view and `/control/runtime/execution` safe projection for provider proposals, pending approvals, tool/browser/MCP status, provider continuation, final response readiness, bounded loop guards, risk level, and safe trace refs. Frontend views display and approval-state data only; they do not execute tools.

Checkpoint limitation after this checkpoint: live provider credential smoke as a required automated test, generic provider routing/model selection, retry/fallback behavior, direct Browser-use SDK execution, broad browser/computer actions, MCP server launch/install, shell/filesystem tools, live OAuth/account sync, auto-fetch, raw transcript/prompt/tool/provider/browser payload persistence, voice, Orb/Face UI, desktop overlay, and proactive behavior were not implemented or required later policy controls.


## Hybrid Intent, Web Search, Grounded Evidence, and Risk-Based Governance Checkpoint

Marvex now has a real hybrid intent path for pre-Voice runtime use. `semantic-router[hybrid]==0.1.14` is declared and uv-resolved, with the exact uv result that this version has no `hybrid` extra; Marvex therefore uses real local `semantic_router.Route` definitions plus Marvex-owned hybrid fallback logic. `llama-index-core>=0.14.22` is adopted narrowly for selector proof through `SingleSelection`; LlamaIndex does not own Core, RuntimeComposition, MemoryRuntime, prompt assembly, or agent planning.

`packages.web_search_runtime` adds SearXNG HTTP/JSON search and DDGS fallback adapters with safe web result/evidence models. SearXNG is preferred when configured; DDGS uses the real `ddgs>=9.14.4` package behind the adapter. `packages.grounded_answer_runtime` validates that grounded answer citations map to web evidence refs before acceptance, and PromptHarnessRuntime can receive bounded web evidence context through `ContextSourceKind.WEB_SEARCH_EVIDENCE`.

Risk governance now allows read/list/search/inspect/summarize by default, requires approval for write/delete/send/upload/install/run/connect/private-account actions, and reserves hard-block for malware, credential theft, injection exploitation, exfiltration, unauthorized account abuse, CAPTCHA/anti-bot bypass, stealth abuse, destructive/payment actions without consent, and policy override attempts.

Checkpoint limitation after this checkpoint: Voice runtime, Orb/Face UI, desktop overlay, proactive behavior, tool execution, MCP install/execute, broad OAuth sync, auto-fetch, browser side effects, and generic provider routing/model selection were either not implemented or required approval/policy control; raw provider/tool/browser/search payload persistence stayed denied by default.


## Adaptive Context, Evidence, Memory Learning, and Governance Checkpoint

Marvex now has route-adaptive prompt/context delivery before Voice. Grounded lookup routes get non-zero evidence budget, citation guidance, and web evidence sections. Memory routes get non-zero memory budget and memory evidence sections. Tool, browser, and MCP routes get eligible capability schema sections plus approval policy context. Clarification routes stay concise and suppress unnecessary blocks intentionally rather than accidentally.

Memory Tree search now has a local semantic/filterable search path with deterministic token-vector scoring, synonym normalization, metadata/hotness ranking, and filters for trust level, recency, entity, topic, source, source type, hotness, and evidence availability. No new embedding dependency was added; `fastembed` or `sentence-transformers` remain future options only if a later goal proves local embeddings are needed.

LearningRuntime now records safe feedback events and produces review-required memory, skill, policy, preference, route-example, and memory-hotness candidates from corrections, ratings, tool outcomes, memory-use feedback, and intent/retrieval failures. It cannot silently mutate skills or policy.

Governance now has granular, reason-coded audit decisions for allow, approval_required, deny, quarantine, and hard_block. MCP allowlist state can be projected from runtime/config/control-plane policy and changes are review-required proposals, not silent source-only mutation.

Checkpoint limitation after this checkpoint: Voice runtime, Orb/Face UI, desktop overlay, proactive behavior, broad live OAuth sync, auto-fetch, policy/skill mutation, generic provider routing/model selection, and paid/cloud-only embeddings were not implemented or required later policy control; arbitrary tool execution required approval and raw sensitive payload persistence stayed denied by default.


## Autonomy Modes and Policy Control Plane Checkpoint

Marvex now has a user-controlled autonomy policy layer before Voice. `packages.capability_runtime.autonomy` defines Locked Down, Ask Before Risky, Auto Marvex, and Custom modes with a capability permission matrix for web search, browser/page read, browser click/type, computer actions, MCP list/execute/install, skills use/update/create, connector OAuth/live sync, auto-fetch, memory/profile writes, semantic memory search, learning mutation candidates, provider retry/fallback, file read/write/delete, external send/upload, and shell command execution policy seams.

Auto Marvex allows safe read/list/search, public web search, public page read/extract, MCP listing, memory search, semantic memory search, trusted MCP execution, auto-fetch/live sync when connector/source policy enables it, memory/profile writes when policy enables them, skill adaptation candidates, and bounded retry/fallback according to the matrix. Side effects remain audited allow/ask/deny/quarantine policy decisions, not blanket hard-blocks. Hard-block is reserved for blacklist abuse only.

Control Plane API and web now expose Runtime Policy / Autonomy Modes with mode selection, a capability matrix, and policy decision audit records. The frontend updates policy only through protected Control Plane API calls and does not execute tools directly or render raw secrets/payloads.

Still not implemented after this checkpoint: Voice runtime, Orb/Face UI, desktop overlay, proactive behavior beyond policy controls/seams, actual generic provider routing/model selection, real broad live OAuth data ingestion workers, untracked background sync, direct shell/file tools, and direct Browser-use SDK task execution. These are classified as not implemented or policy-controlled seams rather than global hard-blocks unless they hit blacklist abuse categories.

## Runtime Completion and Phase Unlock Checkpoint

Marvex now has the pre-Voice runtime completion layer needed to move beyond foundation-only behavior. Grounded-answer turns are first-class intent routes; web search evidence and Memory Tree evidence enter ContextRuntime, PromptHarnessRuntime, and citation-validated final answers. Prompt harness assembly now uses route profiles with non-zero evidence, memory, tool-schema, skill, and approval-policy budgets where relevant while simple chat stays lean.

IntentRuntime exposes multi-step plans for mixed current-web/repo/grounded-answer requests and keeps clarification as a stop condition for ambiguous commands. CapabilityRuntime has dynamic tool selection with provider-facing schemas limited to eligible tools, plus per-request AutonomyPolicy decisions for browser, MCP, shell, file, connector, learning, and provider fallback actions. ProviderSelectionRuntime owns model/provider selection and fallback decisions without moving provider construction out of ProviderRuntime. Assistant turn integration has explicit recovery models for provider, tool, web-search, memory-retrieval, and clarification fallback paths.

LearningRuntime now has a feedback ingestion and pipeline runner path. Feedback events can create reviewable memory, skill, policy, preference, route-example, source-preference, and memory-hotness candidates; candidate application is policy-controlled and audited, with Auto Marvex allowed to apply safe candidates. ConnectorRuntime now has a mock/local sync runner that uses Authlib-backed OAuth metadata, canonicalizes connector documents, chunks them, and feeds MemoryTreeRuntime; scheduled auto-fetch is policy-controlled and audited, with no untracked background sync.

Control Plane API and web now expose protected feedback/learning APIs and views alongside autonomy mode selection, runtime policy matrix, connector sync settings, auto-fetch controls, tool/MCP/skill policy views, audit trail, memory scoring, prompt/evidence diagnostics, and runtime execution projections. Frontend mutation remains through protected APIs only.

MCP launch/install, shell command execution, and file write/delete are no longer treated as broad governance hard-blocks. They are policy-controlled at the AutonomyPolicy level; actual shell and file execution adapters remain not implemented runtime adapters. Hard-block remains reserved for blacklist abuse only.

Still not implemented after this checkpoint: Voice runtime, Orb/Face UI, desktop overlay, proactive behavior worker, real external OAuth credential sync against user accounts, direct Browser-use SDK task execution, and actual shell/file execution adapters. Real external OAuth sync requires user credentials/provider app configuration and must continue to avoid raw secret persistence. Shell/file adapters require a separate execution-adapter implementation and validation slice.
## Validation Baseline

Initial baseline before this cleanup:

- `git branch --show-current` -> `main`
- latest commit -> `8405c33 feat: deepen assistant intelligence tool runtime`
- `git status --short` -> clean
- upstream divergence -> `0 0`
- `python scripts/run_all_checks.py` -> PASS all validation checks passed
- `python -m pytest tests\capability_runtime tests\assistant_turn_integration -q` -> 28 passed

## Current State

Marvex remains on the Assistant OS infrastructure path. Existing foundations are now classified in `docs/GOVERNANCE_CLASSIFICATION.md` so code existence is not treated as product approval.

Documented implementation surfaces: provider foundation contracts, the assistant envelope contracts, runtime completion foundations, the minimal local CoreService entrypoint, and the local-only VoiceWorker runtime contract listed in `docs/CONTRACT_APPROVALS.md`.

Bounded foundations: assistant turn integration, telemetry, Local API, Control Plane API, Control Plane web, CapabilityRuntime, tool execution foundations, MCP adapter, MemoryRuntime, MarketplaceRuntime, SessionRuntime, IntentRuntime, ContextRuntime, PromptHarnessRuntime, and VoiceRuntime. `packages/core/service.py` is the pure Core orchestration foundation; `services/core/main.py` is the minimal local runnable Core service entrypoint. VoiceWorker is no longer a future service placeholder: it is listed for local-only worker implementation inside its documented boundaries. These foundations may be maintained and tested, but expansion outside their documented scope requires updates to `docs/CONTRACT_APPROVALS.md`, this status file, validation gates, and relevant architecture docs.

Experimental seams: browser/computer-use adapter seams are present for policy-gated proposals and bounded adapter proofs only. They are not general product permission for browser or desktop automation.

Future service contracts: `services/*` placeholders remain README-only except for the approved minimal `services/core` local entrypoint files. Desktop agent, shell/orb UI, proactive behavior, and vision remain future product behavior for now; VoiceWorker is listed only for the local-only worker runtime surface described above.

## Cleanup Result

This governance cleanup hardened the repository around two current risks:

- `packages/capability_runtime/execution.py` must stay a re-export facade, with execution models split into focused CapabilityRuntime modules.
- `packages/assistant_turn_integration/spine.py` must stay a narrow composition spine, with stage logic extracted into focused assistant turn integration modules.

CapabilityRuntime remains authoritative for permissions, policy decisions, execution requests, result envelopes, and loop guards. Assistant turn integration coordinates documented runtime layers but must not become the assistant brain. Core remains orchestration-only. ProviderRuntime remains provider construction only. Local API and Control Plane remain HTTP/auth/JSON and safe projection layers only.

## Blocked

Blocked without explicit future approval: new product features, new dependencies, generic provider routing/model selection, arbitrary tool execution, shell execution, filesystem write/edit/delete tools, arbitrary MCP install/launch/execute, arbitrary skill install/remote loading/script execution, uncontrolled browser/computer/desktop automation, raw prompt/transcript/tool/provider/browser/audio payload persistence by default, voice behavior outside the bounded VoiceRuntime foundation, Orb, desktop overlay, proactive behavior, and vision.

## Next Recommended Goal

Recommended next goal: Voice Worker Process Boundary and Local Microphone Runtime. Keep the in-process VoiceRuntime contracts stable, add an explicit worker/service contract, and prove local capture/playback process boundaries without Orb/Face UI, desktop overlay, vision, proactive behavior, or raw audio/transcript persistence by default.

Browser-use backend remains disabled for direct SDK execution; the controlled adapter proof exposes only safe status, allowed categories, and blocker metadata.

## Cognition Runtime and Agentic Turn Loop Checkpoint

Marvex now has a Cognition Runtime bounded foundation and a bounded Agentic Turn Loop in the local Core service entrypoint. Cognition Runtime assembles intent, route-adaptive context, memory evidence refs, web evidence refs, prompt plan projections, and a safe step plan without importing provider adapters, worker internals, or subprocesses.

The live Core worker-backed turn now uses the Assistant Turn Spine shape instead of a one-shot reflex route. Core receives a turn, runs cognition assembly, drives a bounded plan/act/observe/finalize loop through existing ProviderWorker and ToolWorker JSONL IPC, returns real calculator results, and emits safe telemetry under one trace id.

The developer-only `scripts/smoke_core_real_provider_adapter.py` proof runs the same Core turn path through ProviderWorker, ProviderRuntime, and the `lmstudio_responses` adapter against a loopback Responses-compatible endpoint. This proves the non-fake provider adapter boundary in the agentic loop without adding a CI network dependency. A live external LM Studio or LiteLLM model smoke remains host-dependent and must still be run manually when that runtime is available.

The developer-only `scripts/smoke_core_real_web_adapter.py` proof runs the same Core grounded-answer path through the real `SearXNGWebSearchAdapter` against a loopback SearXNG-compatible JSON endpoint. This proves the configured web-search adapter boundary in the agentic loop without adding a CI internet dependency. A live internet SearXNG or DDGS smoke remains host/network-dependent and must still be run manually when that runtime is available.

Runtime smoke proof on this host: with the inherited broken proxy variables cleared for the command process, Core completed a live LM Studio Responses turn through ProviderWorker and returned a real provider response under `trace-smoke-real-provider`. The same unproxied runtime path completed a live DDGS grounded-answer turn under `trace-smoke-real-web-unproxied-fixed`, returned five evidence refs, and validated citations without fabricating. The default CI path still uses fake provider/search or loopback adapter smokes only.

Grounding is enforced for fresh and grounded turns. Core searches without asking when grounding is required, validates citation ids against evidence refs, returns cited answers when evidence exists, and returns an evidence-missing response instead of fabricating when no evidence exists. Demo memory evidence can be injected for local runtime smokes to prove memory refs flow into grounded answers.

approval resume works for risky actions through explicit approval request ids and approve, deny, or cancel decisions. Approve resumes the same trace_id/turn_id through the policy-controlled worker boundary; deny and cancel return structured blocked results. Broad dangerous shell/file execution adapters, desktop/browser/computer execution, voice product shell, proactive behavior, remote production daemon behavior, richer approval UX, and generic provider routing/model selection remain future work.

## Agentic Tools and Intent Routing Checkpoint

Marvex now has a real policy-gated tool breadth slice and a smarter live intent/planner slice. ToolWorker executes all existing safe built-ins, a read-only sandboxed file read/list/search capability under an explicit root, and allowlisted MCP calls through `McpSdkAdapter` with a deterministic local fixture for CI. `governance_audit.classify_governance_action` is integrated into live dispatch alongside configurable per-request autonomy mode; file traversal, non-allowlisted MCP tools, unsafe requests, and side-effect actions return structured deny, hard-block, or approval-required results instead of fake success.

IntentRuntime now uses an explicit deterministic offline encoder seam (`deterministic_local_encoder`) for semantic route selection, while deterministic safety and explicit infrastructure intents remain authoritative for clear memory, MCP, skill, file, connector, settings, risky, and unsafe prompts. The runtime-facing canonical contract is `SafeIntentProjection`; legacy `IntentDecision`/route-family ports and adapters are compatibility-only and are not imported by Core or Cognition Runtime.

Core now consumes `cognition.intent_plan` for worker-backed route execution. Capability, file, MCP, memory, skill, connector, settings, browser/computer-use, web/grounded, risky, unsafe, clarification, and provider-simple-chat intents have explicit execution or safe policy-projection paths. Browser/computer-use, connector live OAuth, skill install/launch, shell execution, file write/delete, arbitrary remote MCP launch/install, voice product shell, desktop agent, Orb/UI, and proactive behavior remain future gated work.
