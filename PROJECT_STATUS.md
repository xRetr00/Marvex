# Project Status

current_phase: voice_worker_runtime_boundary_checkpoint

implementation_status: voice_worker_runtime_boundary_checkpoint

accepted_docs: true

current_governance_gate:
Voice Worker Runtime Boundary Checkpoint

## Voice Worker Runtime Boundary Checkpoint

Marvex now has the first dedicated local voice worker boundary in `packages.voice_worker_runtime`. The worker layer owns explicit local lifecycle commands, heartbeat/status, loopback-only process launch, microphone and playback adapters, safe model asset root validation, worker events, and safe Control Plane projections. It is local-only, rejects remote process bindings, does not auto-start, and does not allow hidden recording or raw audio/transcript/generated-audio persistence by default.

`sounddevice==0.5.5` is declared as the local audio device dependency and isolated behind `SoundDeviceAudioAdapter`; tests use `FakeLocalAudioAdapter` because CI cannot validate physical microphone or speaker hardware. The worker can list/test fake devices, select devices through config reload, capture PCM frames without persistence, run a bounded live capture cycle with injected/mockable VAD decisions, pre-roll, silence cutoff, tail padding summaries, and max-utterance stop before assistant dispatch, run a manual voice turn through VAD/STT/policy/assistant/TTS/playback event stages, emit safe event-count telemetry summaries, and interrupt playback for barge-in. `VoiceWorkerBackendRuntime` now checks installed local assets plus package import/version availability and uses package-specific model adapters for Moonshine v2, SenseVoice-Small/FunASR, Kokoro-ONNX, and Piper only after readiness passes, while safe command summaries suppress raw transcripts and synthesis text. Non-persistent in-memory audio refs and generated-audio refs now support runner handoffs without rendering PCM bytes. Real model downloads, real live heavy inference smoke against installed assets, package-specific sherpa-onnx KWS invocation, and physical device smoke remain explicit local/manual work.

Control Plane API/web now exposes protected voice worker status, start/stop/pause/resume, config reload, microphone and playback tests, device lists/selectors, wakeword/STT/TTS test commands, model install/remove, backend/model readiness, safe telemetry counts, backend switching, and active voice switching. Model asset handling now reports missing files as `not_installed`, checksum mismatches as `blocked`, and Hey Marvex wakeword tests as not-ready until wakeword is enabled and the sherpa-onnx KWS asset is installed. VoiceWorkerRuntime does not own AutonomyPolicy, CapabilityRuntime, assistant turn execution policy, RuntimeComposition supervision, or Local API internals.

## Voice Runtime Foundation Checkpoint

Marvex now has a bounded VoiceRuntime foundation after runtime completion and phase unlock. `packages.voice_runtime` owns voice I/O orchestration only: wakeword, VAD, audio ring buffers, chunk aggregation, STT/TTS backend selection, model/voice registries, sentence clamping, queued speech, barge-in state, early safe filler speech, voice personality settings, safe voice turn envelopes, and safe Control Plane projections.

Adopted voice dependencies are `moonshine-voice==0.0.59`, `funasr==1.3.1`, `sherpa-onnx==1.13.2`, `sherpa-onnx-core==1.13.2`, `kokoro-onnx==0.5.0`, `piper-tts==1.4.2`, `stream2sentence==0.3.2`, `silero-vad==6.2.1`, and `webrtcvad-wheels==2.0.14`. The uv compatibility probe resolved successfully; `uv run python -m pip check` initially found missing `sherpa-onnx-core`, and adding the explicit dependency fixed the check.

Control Plane API/web now exposes protected Voice Runtime status, STT/TTS backend selectors, active voice selection, voice/model download request surfaces, STT/TTS test actions, wakeword settings, VAD/barge-in/early speech/personality settings, audio retention policy, backend health, and telemetry summaries. Frontend voice controls call protected backend APIs and do not run audio engines directly.

Voice turns use injected assistant-turn and policy callbacks so VoiceRuntime does not own intent routing, tools, memory, provider routing, CapabilityRuntime, AutonomyPolicy, or visual UI. Prompt-injection-like transcripts can be quarantined before assistant execution; ambiguous voice commands ask clarification; risky actions produce voice approval prompts without execution. Wakeword 24/7 support is explicit, visible, policy-controlled, and disabled by default. Raw audio, generated audio, transcripts, backend internals, provider payloads, tool payloads, and secrets are not persisted or rendered by default.

Still not implemented after this checkpoint: Orb/Face UI, desktop overlay, final visual assistant shell, vision, proactive non-voice behavior, separate always-running voice worker process supervision, real external OAuth credential sync against user accounts, direct Browser-use SDK task execution, and actual shell/file execution adapters. These remain future explicit goals or policy-controlled/not-implemented seams.


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

`guardrails-ai` is blocked in the current Python 3.12.0 environment because pip found no matching distribution. The Guardrails adapter remains a tested safe-projection validation seam with an explicit blocked backend reason; Guardrails cannot assemble prompts or run automatic retry loops.

`browser-use==0.11.13` is adopted as a main-environment dependency for import-backed adapter proof. Latest `browser-use==0.12.6` remains blocked because it pins `openai==2.16.0`, conflicting with Marvex's OpenAI Agents-compatible `openai==2.37.0`. The browser-use backend remains disabled for execution, CapabilityRuntime approval remains mandatory, and Playwright `1.60.0` remains the low-level browser SDK path.

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

Approval resume now distinguishes approved, denied, and cancelled outcomes in safe projections. Approved Playwright-backed browser navigation can execute after CapabilityRuntime approval when a page boundary is supplied; click/type remain approval-gated and no browser-use execution was promoted. Trace search and Control Plane summaries expose only counts/status booleans for proposal, approval, execution, continuation, and final response state.

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

Approved implementation surfaces: provider foundation contracts and the approved assistant envelope contracts.

Bounded foundations: assistant turn integration, telemetry, Local API, Control Plane API, Control Plane web, CapabilityRuntime, tool execution foundations, MCP adapter, MemoryRuntime, MarketplaceRuntime, SessionRuntime, IntentRuntime, ContextRuntime, PromptHarnessRuntime, and VoiceRuntime. These foundations may be maintained and tested, but expansion is blocked unless a future goal updates `docs/CONTRACT_APPROVALS.md`, this status file, validation gates, and relevant architecture docs.

Experimental seams: browser/computer-use adapter seams are present for policy-gated proposals and bounded adapter proofs only. They are not general product permission for browser or desktop automation.

Future service contracts: `services/*` placeholders remain README-only. Separate voice worker service processes, desktop agent, shell/orb UI, proactive behavior, and vision remain future/forbidden product behavior for now.

## Cleanup Result

This governance cleanup hardened the repository around two current risks:

- `packages/capability_runtime/execution.py` must stay a re-export facade, with execution models split into focused CapabilityRuntime modules.
- `packages/assistant_turn_integration/spine.py` must stay a narrow composition spine, with stage logic extracted into focused assistant turn integration modules.

CapabilityRuntime remains authoritative for permissions, approvals, execution requests, result envelopes, and loop guards. Assistant turn integration coordinates approved runtime layers but must not become the assistant brain. Core remains orchestration-only. ProviderRuntime remains provider construction only. Local API and Control Plane remain HTTP/auth/JSON and safe projection layers only.

## Blocked

Blocked without explicit future approval: new product features, new dependencies, generic provider routing/model selection, arbitrary tool execution, shell execution, filesystem write/edit/delete tools, arbitrary MCP install/launch/execute, arbitrary skill install/remote loading/script execution, uncontrolled browser/computer/desktop automation, raw prompt/transcript/tool/provider/browser/audio payload persistence by default, voice behavior outside the bounded VoiceRuntime foundation, Orb, desktop overlay, proactive behavior, and vision.

## Next Recommended Goal

Recommended next goal: Voice Worker Process Boundary and Local Microphone Runtime. Keep the in-process VoiceRuntime contracts stable, add an explicit worker/service contract, and prove local capture/playback process boundaries without Orb/Face UI, desktop overlay, vision, proactive behavior, or raw audio/transcript persistence by default.

Browser-use backend remains disabled for direct SDK execution; the controlled adapter proof exposes only safe status, allowed categories, and blocker metadata.
