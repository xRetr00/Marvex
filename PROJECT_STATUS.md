# Project Status

current_phase: end_to_end_assistant_turn_integration_foundation_complete

implementation_status: end_to_end_assistant_turn_integration_foundation_complete

accepted_docs: true

current_governance_gate:

End-to-End Assistant Turn Integration Foundation Complete

## Validation Baseline

Latest full validation baseline from End-to-End Assistant Turn Integration Foundation:

- `python scripts\run_all_checks.py` -> PASS all validation checks passed
- `python -m pytest -q` -> 854 passed, 1 skipped
- `python -m pip check` -> No broken requirements found.
- `npm run build` from `apps/control_plane_web` -> built
- `npm test` from `apps/control_plane_web` -> 2 passed


## End-to-End Assistant Turn Integration Foundation State

End-to-End Assistant Turn Integration Foundation is complete as a bounded assistant-turn spine in `packages.assistant_turn_integration`.

Implemented: Local API turn integration through injected handlers, safe session/conversation linkage, IntentRuntime route decisions, ContextRuntime safe context selection, PromptHarnessRuntime bounded prompt plans, AssistantRuntime provider-stage/lifecycle coordination, CapabilityRuntime provider tool-call proposal handling, pending approval state, safe built-in calculator execution through approved `CapabilityExecutionRequest`, provider continuation/final response readiness, telemetry trace persistence through safe summaries, and Control Plane trace/approval/runtime visibility through safe projections.

Local API owns HTTP/auth/JSON only. CapabilityRuntime owns policy/approval/dispatch. IntentRuntime owns intent/route decisions. ContextRuntime owns context selection. PromptHarnessRuntime owns prompt plan construction. AssistantRuntime owns lifecycle coordination. Telemetry owns trace persistence. Control Plane owns safe visibility and approval APIs only.

Blocked: voice, Orb, desktop overlay, proactive behavior, arbitrary browser/computer actions, shell execution, filesystem write/edit/delete, raw prompt/transcript/tool/provider/browser payload persistence by default, generic provider routing/model selection, and RuntimeComposition becoming an assistant brain.

Recommended next: add a narrow persisted trace plus local service composition proof for the integrated turn, keeping storage in Telemetry and startup in local_service_startup.
## Intent, Context, and Prompt Harness Foundation State

Intent, Context, and Prompt Harness Foundation is complete as a safe routing, context selection, prompt planning, compaction, validation, and telemetry-summary boundary.

Implemented: IntentRuntime exists with intent refs, candidates, classification requests/results, confidence buckets, route decisions, risk signals, ambiguity signals, clarification decisions, and safe intent projections. ContextRuntime/PromptHarness now owns context source refs, candidates, eligibility decisions, context packs, budgets, delivery policy, exclusion reasons, bounded prompt sections, prompt harness plans, prompt assembly requests/results, budget reports, compaction/offload/tool-result-clearing decisions, planning readiness, validation results, and telemetry-safe harness summaries.

CapabilityRuntime remains authoritative for capability policy, permissions, eligibility, dispatch, approvals, execution requests, result envelopes, and loop guards. The harness can select eligible capability/tool/skill/MCP schema projections by intent/context, but it cannot approve execution or bypass policy.

Adapter seams exist for Semantic Router, Guardrails-style validation, LlamaIndex routers/selectors, LangChain/LangGraph context patterns, OpenAI Agents SDK guardrails/context patterns, Anthropic context engineering patterns, and awesome harness/context reference resources. No new runtime dependency was added; unsafe or broad libraries remain disabled/reference-only until a future decision.

Blocked: raw prompt/transcript/provider/tool/browser payload persistence by default, all-tools dumping, all-skills dumping, all-memory dumping, embeddings/vector search without a separate decision, autonomous planners, recursive loops, browser/computer actions, UI, voice, desktop, vision, proactive behavior, and generic provider routing.

Recommended next: add a narrow AssistantRuntime consumption proof for safe `PromptHarnessPlan` projections, without provider-specific prompt ownership, raw prompt persistence, or generic provider routing.
## Control Plane Foundation State

Control Plane Foundation is complete as a protected local admin/control foundation. It adds a Human Approval API, safe Control Plane snapshot boundary, isolated web frontend, typed client, and validation gates.

Control Plane API must not own policy. It exposes local HTTP/auth/JSON-only approval and safe projection endpoints while CapabilityRuntime remains authoritative for approvals, permissions, risk classification, execution modes, approved execution requests, dispatch policy, execution state, and loop guards.

Implemented: protected approval list/read/approve/deny flows, safe approval decision reason handling, safe provider/capability/tool/MCP/skill/telemetry/trace/memory/session/agent-loop/settings snapshot projections, token-safe auth failure behavior, isolated React/TypeScript/Vite web app, TanStack Query API client, Zod response validation, dashboard/views, and dedicated boundary gates.

Complete: the web app displays dashboard, approvals, traces, telemetry, providers, capabilities/tools, MCP, skills, memory/session safe views, and settings through safe API projections only. Frontend build and tests pass.

Blocked: direct Control Plane tool execution, frontend Python imports, frontend tool execution, raw secrets/tokens/API keys/environment values, raw prompts/transcripts/tool payloads/browser DOM/screenshots, arbitrary remote access, Orb, desktop overlay, voice UI, vision UI, proactive behavior UI, and any policy bypass around CapabilityRuntime approvals. Recommended next: add a narrow local service composition path that serves Control Plane API plus static web assets on loopback with generated local bearer-token handoff, without remote binding or daemon supervision.
## Agent Execution Loop and Tool-Orchestrated Turn Foundation State

Agent Execution Loop and Tool-Orchestrated Turn Foundation is complete as a bounded model/API-ready loop foundation. CapabilityRuntime remains authoritative for permission decisions, approval requirements, approval decisions, execution request validation, result envelopes, loop guards, stop reasons, safe continuations, and telemetry-safe summaries.

Implemented: `AgentLoopState`, `AgentLoopStep`, `AgentLoopDecision`, `AgentLoopStopReason`, `AgentLoopGuardResult`, `ToolOrchestrationState`, `PendingApprovalState`, `ToolContinuationState`, `SafeAgentLoopProjection`, tool denial envelopes, safe continuation readiness, lifecycle summary linkage, and a safe built-in calculator execution proof through an approved `CapabilityExecutionRequest`.

provider tool calls are proposals, not execution permission. risky actions can pause for human approval, denial returns a safe result envelope, and approved safe tools can execute only through request objects validated by CapabilityRuntime policy. AssistantRuntime coordinates only safe tool-orchestrated turn summaries and does not import adapters or execute tools.

Blocked: uncontrolled autonomous agents, shell/terminal execution, filesystem write/edit/delete tools, arbitrary browser/computer actions, credential entry or extraction, purchase/payment/checkout, CAPTCHA or anti-bot bypass, UI, voice, desktop control, vision, proactive behavior, generic provider routing, raw prompts/transcripts/tool/provider payload persistence by default, and adapter bypass of CapabilityRuntime policy.

Recommended next: add a narrow approval-service/API readiness boundary that can hold, project, and resolve pending approval refs without adding UI, desktop/browser execution, provider routing, or raw payload persistence.
## Full Tooling and Computer Use Foundation State

Full Tooling and Computer Use Foundation is complete as a policy-gated adapter
foundation. CapabilityRuntime remains authoritative for risk, side-effect
classification, permission decisions, human approval requirements, approval
prompts, approval decisions, execution modes, execution requests, result
envelopes, context delivery, compaction, loop guards, and safe telemetry
summaries.

Implemented: `ToolRiskLevel`, `ToolSideEffectLevel`,
`CapabilityExecutionMode`, `ToolExecutionPolicy`, approval request/decision
models, pending approval projections, denial result envelopes, eligible-only
tool schema delivery, repeated-failure/human-approval loop guard state, and
tooling telemetry safe summaries. Safe built-ins now cover calculator, UTC
time/date, capability diagnostics, and injected read-only repo status snapshots.

Adapter foundations now exist for Playwright browser automation, Browser-use,
OpenAI Computer Use, OpenAI Agents SDK tool compatibility, OpenAI function tool
proposals, LM Studio local tool proposals, LiteLLM gateway tool proposals, and
existing MCP SDK tools. Playwright is adopted behind
`packages.adapters.capabilities.browser` only. Browser-use backend remains
disabled pending a future policy review. OpenAI Agents SDK package adoption is
blocked for now because `openai-agents==0.17.2` requires `openai>=2.26.0` while
Marvex currently pins `openai==2.24.0`; the compatibility seam exists without
importing the SDK package.

Blocked: real shell/terminal execution, file write/edit/delete tools,
credential entry or extraction, purchase/payment/checkout, sensitive form
submission without future explicit approval flow, CAPTCHA/anti-bot bypass,
stealth/proxy scraping, arbitrary desktop OS control, raw screenshots, raw DOM,
raw page text, raw tool input/output, prompts, transcripts, tokens,
credentials, provider payload persistence by default, and any adapter bypass of
CapabilityRuntime policy.

Recommended next: add a narrow approval-service/API surface that can hold and
resolve `PendingApprovalState` without adding UI, browser execution, desktop
control, or provider runtime integration.


## Skills Runtime Foundation State

Skills Runtime Foundation is complete as a safe representation, validation,
selection, and context-delivery foundation. Skill is bounded capability context:
a locally referenced package of instructions, resources, and optional script
metadata that can contribute bounded context only after validation and
CapabilityRuntime eligibility/context delivery policy.

`packages.skills_runtime` owns `SkillRef`, `SkillManifest`,
`SkillValidationResult`, `SkillEligibilityDecision`, `SkillPromptContribution`,
`SkillResourceRef`, safe skill projections, and a deterministic fake skill
package for tests only. The capability adapter skill seam now delegates to
SkillsRuntime instead of owning skill primitives.

CapabilityRuntime remains authoritative for capability refs, manifests,
eligibility decisions, context delivery policy, compaction policy, and context
packs. SkillsRuntime can project skills into CapabilityRuntime-owned models, but
skills cannot override Marvex policy.

Blocked: real script execution, arbitrary skill install, remote skill loading,
shell/filesystem/browser/desktop/OS access, prompt rewrites, hidden policy
override, raw prompt/transcript/tool payload persistence by default, Core
integration, Local API integration, RuntimeComposition integration,
ProviderRuntime integration, Telemetry ownership, AssistantRuntime integration,
MemoryRuntime integration, SessionRuntime integration, local service startup
registration, MCP adapter ownership, UI, voice, desktop, vision, proactive
behavior, provider routing, and model selection.


## MCP Adapter Foundation State

MCP Adapter Foundation is complete as a safe, allowlisted, policy-gated adapter foundation. `packages.adapters.capabilities.mcp` now uses the official MCP Python SDK for protocol mechanics through an injected `ClientSession` boundary, while CapabilityRuntime remains authoritative for manifests, permission decisions, call proposals, execution requests, result envelopes, and safe projections.

The adapter can initialize/list tools only for approved server refs, convert allowed MCP SDK tool metadata into sanitized `CapabilityManifest` projections, create permission-gated call proposals, and call SDK tools only from approved `CapabilityExecutionRequest` envelopes. Safe result envelopes expose status, content counts/types, and structured-content presence only; raw input/output persistence remains false.

Blocked: arbitrary MCP registry install, hidden server launch, stdio process creation, auto-execution, shell/filesystem/browser/desktop/network tool enablement, raw payload persistence, Core integration, AssistantRuntime integration, ProviderRuntime integration, RuntimeComposition integration, Local API integration, service/CLI integration, and runtime turn-flow integration.


## Assistant Stage Lifecycle Foundation State

The Assistant Stage Lifecycle Foundation is complete as an AssistantRuntime-owned
one-turn lifecycle layer. `packages.assistant_runtime.lifecycle` now defines
`AssistantStageName`, `AssistantStageResult`, `AssistantTurnLifecycleSummary`,
safe lifecycle projections, and forward-only lifecycle transition validation.

The lifecycle order is explicit: input normalization, safe
session/conversation linkage, runtime state snapshot readiness, memory read
policy readiness, provider-stage preparation, provider result consumption, final
response assembly, memory write candidate readiness, memory policy hooks, and
telemetry trace linkage.

Lifecycle summaries safely link `trace_id`, `turn_id`, safe `session_ref`, safe
`conversation_ref`, provider response id presence, previous response id
presence, provider/memory/output reference counts, memory read/write/forget
readiness, memory policy decision counts, telemetry event counts, and persistent
trace linkage readiness. They explicitly keep `transcript_persisted: false` and
`raw_payload_persisted: false`.

AssistantRuntime does not store raw prompts, raw assistant outputs, provider
payloads, provider outputs, provider response ids, previous response ids,
transcripts, tokens, secrets, credentials, environment values, or memory
content. MemoryRuntime still owns memory refs, records, policy decisions, read
queries, write candidates, forget requests, stores, and projections.
SessionRuntime still owns session/conversation linkage and projections.
Telemetry still owns trace event safety, persistence, and reads. Core remains
orchestration-only, Local API remains HTTP/auth/JSON-only, RuntimeComposition
remains explicit approved-path composition, ProviderRuntime remains provider
construction-only, and local_service_startup remains startup/discovery metadata
only.

Boundary validation now tracks lifecycle primitive ownership and permits
AssistantRuntime lifecycle code to mention provider response ids only for
presence/absence in safe summaries. Lifecycle ownership is blocked from Core,
Local API, local_service_startup, RuntimeComposition, ProviderRuntime, and
telemetry Python source.

## Memory Foundation State

The Memory Foundation is complete. It defines `packages.memory_runtime` as the
memory owner boundary.
MemoryRuntime now owns safe `MemoryRef`, `MemoryRecord`, `MemoryWriteCandidate`,
`MemoryPolicyDecision`, `MemoryReadQuery`, `MemoryForgetRequest`,
`MemoryReadResult`, `MemoryForgetResult`, safe projections, and an explicit
instance-owned `CurrentProcessMemoryStore` proof. The store is current-process
only and is not long-term recall, file persistence, embeddings, vector search,
or product memory.

Memory means policy-governed assistant recall material such as safe facts,
preferences, instructions, or summaries. It is not a transcript store, telemetry
store, session store, provider state store, prompt cache, vector database, tool
state, UI state, voice state, desktop context, vision state, proactive state,
router, model selector, daemon, or WebSocket/event stream. Memory records may
link to `session_ref`, `conversation_ref`, `trace_id`, and `turn_id`, but raw
transcripts, raw prompts, provider payloads, provider outputs, tokens,
credentials, environment values, and secrets are rejected by default.

Memory write candidates remain pending until explicit policy approval. A record
can be built only from an approved candidate plus an approved policy decision.
Generic read and forget request paths require `policy_status: approved` before
store dispatch. Forget/delete is represented by `MemoryRef` and returns a safe
result without exposing stored content. Core, Local API, RuntimeComposition,
ProviderRuntime, telemetry, AssistantRuntime, SessionRuntime, and
local_service_startup must not own memory storage or recall.

## Session And Conversation Foundation State

The Session and Conversation Foundation is complete. `packages.session_runtime`
owns safe session/conversation references, turn linkage metadata, safe session
projections, safe conversation projections, and an optional
current-process-only registry. A session is the current assistant interaction
container; a conversation is the logical user-visible grouping. Both are safe
references only in this foundation.

SessionRuntime can build safe linkage from `AssistantTurnInput` without storing
user-visible input, metadata bodies, provider continuity values, raw prompts, or
transcripts. Telemetry readers may project safe `session_ref` and
`conversation_ref` objects beside `trace_id` and `turn_id`, but telemetry remains
trace persistence/read ownership rather than session ownership. The foundation
stores only `previous_response_id` presence and `transcript_persisted: false`.

Full transcripts, hidden history, long-term memory, embeddings/vector search,
tool state, UI state, voice state, desktop context, vision state, proactive
behavior, generic provider routing, retry/fallback, model selection, daemon
supervision, and WebSocket/events remain blocked. Core, Local API,
RuntimeComposition, ProviderRuntime, telemetry, and local_service_startup must
not become session stores or lifecycle owners.

## Assistant Runtime State Foundation State

The Assistant Runtime State Foundation is complete as a narrow
AssistantRuntime-owned state layer for one assistant turn. AssistantRuntime now
defines safe turn snapshots, execution summaries, and transition records that
link runtime state to telemetry through `trace_id` and `turn_id` without storing
raw prompts, provider payloads, provider outputs, tokens, transcripts, or session
bodies. `previous_response_id` remains explicit caller input only and is exposed
in state snapshots as presence/absence, not as a stored value. Session readiness
is reference-only: `session_ref` presence can be represented, but full
sessions/history, transcript persistence, memory, tools, UI, voice, desktop,
vision, proactive behavior, generic provider routing, retry/fallback, model
selection, daemon supervision, and WebSocket/events remain blocked.

Boundary validation now also prevents AssistantRuntime state primitive ownership
from drifting into Core, Local API, local service startup, RuntimeComposition,
ProviderRuntime, or telemetry. Local API remains HTTP/auth/JSON-only,
RuntimeComposition remains explicit composition-only, telemetry remains trace
safety/persistence/read ownership rather than assistant state storage, Core
remains orchestration-only, and ProviderRuntime remains provider construction
only.

## Telemetry Persistence Foundation State

Task 146 adds telemetry-owned local trace persistence. `PersistentTraceStore`
writes safe newline-delimited JSON records to an explicit local-user-scoped file,
sanitizes event messages and `TraceEvent.data` before persistence, rotates by
bounded file size/count, skips malformed stored records during reads, and raises
safe `TELEMETRY_WRITE_FAILED` errors on write failure. Local API remains an
injected auth/HTTP/JSON access layer, RuntimeComposition remains explicit
composition only, Core remains storage-format blind, and ProviderRuntime remains
telemetry-persistence blind.

## Local Runtime API Foundation Completion State

The Local Runtime API Foundation is complete as a future Shell/CLI-facing local
service foundation. A future client can locate token-redacted loopback metadata,
check public `/health` and `/version`, and call protected `/v1/turns` plus
`GET /v1/traces/{trace_id}` through explicit bearer-auth paths. Discovery files
remain local-user-scoped and never contain raw bearer tokens; protected calls
require a private startup token handoff outside public metadata. Current trace
reads remain same-process, auth-protected, telemetry-owned safe projections.
Local API stays HTTP/auth/JSON only, local service startup owns startup/token and
discovery metadata, RuntimeComposition stays explicit composition only, and
Core/ProviderRuntime remain token/lifecycle/discovery blind.

Recent local API/runtime milestones:

- RuntimeComposition owns explicit fake and LM Studio Responses
  AssistantRuntime bridge proofs; CLI uses only explicit proof flags for those
  paths and default CLI behavior remains provider-foundation scoped.
- Local API now has public loopback `/health` and `/version`, protected fake
  `/v1/turns`, and protected injected `GET /v1/traces/{trace_id}`. Local API
  owns HTTP/auth/JSON only and receives execution/trace behavior by injection.
- The developer-only fake `/v1/turns` runner shares one current-process
  `InMemoryTraceReader` instance between fake turn recording and protected trace
  reads. Task 129 smoke verified five safe projected events for the same trace.
- Task 130 decides the next real-provider local API step: add only an explicit
  LM Studio Responses developer runner/mode
  `assistant_runtime_lmstudio_responses`, with explicit request `model`, no
  preflight enforcement, no generic provider routing, no persistence, no
  sessions/history, and no service daemon behavior.
- Task 131 implements that explicit developer-only runner/handler path. The
  manual runner injects one current-process `InMemoryTraceReader` for both
  telemetry recording and protected trace reads. Local API still receives only
  injected handler/reader callables.
- Task 132 records a manual LM Studio local API smoke. The local API runner,
  auth, mapped provider-error response, and protected trace read worked
  end-to-end on 2026-05-16, but LM Studio returned `AuthenticationError`
  because the current local server requires a valid local API token and rejected
  the placeholder SDK key. No runtime code changed.
- Task 133 decides the LM Studio token path as docs-only: provider credentials
  belong to ProviderRuntime plus the LM Studio adapter config, may be passed by
  the explicit developer-only RuntimeComposition runner, and must not enter
  Local API, Core, AssistantRuntime, request envelopes, traces, logs, or errors.
- Task 134 implements the narrow LM Studio-only token path:
  `ProviderRuntimeConfig.lmstudio_responses_api_key` maps to
  `LMStudioResponsesProviderConfig(api_key=...)`, and the developer-only LM
  Studio local API runner reads `MARVEX_LMSTUDIO_API_KEY` without printing or
  recording its value. Local API, Core, AssistantRuntime, telemetry, default
  CLI behavior, request bodies, and `provider_options` remain provider-token
  blind.
- Task 136 records a token-backed LM Studio local API smoke. With the provider
  token supplied from local environment only, `/health`, `/version`, protected
  `/v1/turns`, and protected `GET /v1/traces/{trace_id}` succeeded for
  `qwen3.5-0.8b`. Trace output exposed only safe current-process projections;
  missing/wrong auth for both protected routes returned `401 AUTH_REQUIRED`.
- Task 137 decides the future service lifecycle and local bearer token startup
  boundary without implementation. A future service runner/startup boundary owns
  generated local bearer token creation, explicit startup/shutdown reporting,
  and any local-user-scoped discovery metadata. Local API remains HTTP/auth/JSON
  only, RuntimeComposition remains composition-only, Core remains service-token
  blind, and trace reads remain auth-protected.
- Task 138 implements the first `packages.local_service_startup` foundation. It
  generates a high-entropy in-memory local bearer token, produces safe public
  startup metadata, defines explicit startup/shutdown semantics, and keeps
  discovery-file writing outside the foundation object itself. Daemon
  supervision, Local API handler integration, RuntimeComposition service
  ownership, Core lifecycle coupling, and ProviderRuntime credential policy
  stay blocked.
- Task 139 adds a narrow Local API service-runner startup proof. It generates
  the local bearer token through `packages.local_service_startup`, injects that
  raw token only into the existing Local API runner call, and prints only safe
  public startup metadata. Discovery-file writes were still blocked at Task
  139. Daemon supervision, auto-restart, RuntimeComposition service ownership,
  generic provider routing, persistent telemetry, sessions/history, and
  WebSocket/events remain blocked.
- Task 140 records a bounded manual smoke for the startup-proof runner:
  `/health` and `/version` returned HTTP 200 on loopback, missing/wrong
  `/v1/turns` auth returned HTTP 401, startup metadata reported token presence
  only, and stdout did not include `local_auth_token`.
- Task 141 decides the first local client discovery path before implementation:
  future discovery metadata may be a local-user-scoped JSON file containing only
  loopback connection metadata and token presence, never raw tokens. Protected
  endpoint access still requires an explicit private token handoff outside that
  file. Discovery-file writes, readers, cleanup, and permissions remain future
  narrow implementation tasks.
- Task 142 implements the first safe discovery metadata writer in
  `packages.local_service_startup`. It writes only token-redacted loopback
  startup metadata under an explicit local-user root, rejects out-of-scope paths
  and remote bind metadata, and does not write bearer tokens or provider
  credentials. Reader/client helpers, cleanup, startup-runner integration, and
  token handoff remain future narrow tasks.
- Task 143 adds the matching safe discovery metadata reader. It reads only
  local-user-scoped JSON metadata, rejects unsafe/raw-token fields and remote
  bind metadata, and returns safe service location/token-presence data for a
  future client without becoming a launcher, registry, token store, or retry
  layer.
- Task 144 wires the approved discovery metadata writer into the startup proof
  runner only when an explicit discovery file path is supplied. The runner
  writes safe loopback metadata, rejects missing or out-of-scope discovery file
  paths, keeps the raw bearer token out of startup output and discovery files,
  and does not add daemon supervision, hidden auto-start, token storage, cleanup,
  client calls, provider routing, retry/fallback, model selection,
  sessions/history, WebSocket/events, or persistent telemetry.
- Task 145 adds `packages.local_api_client` as a narrow future Shell/CLI
  connection proof helper. It reads safe discovery metadata, validates loopback
  and token-redaction rules, calls public readiness endpoints without auth, and
  calls protected `/v1/turns` plus `GET /v1/traces/{trace_id}` only when the
  caller supplies the local bearer token per request. The discovery file still
  never stores the raw token; private token handoff remains outside public
  discovery metadata.

## Current Foundation Capabilities

Provider Foundation completed:

- approved Pydantic provider-foundation contracts, schema generation, and schema
  version policy
- `ProviderPort` as the minimal provider boundary
- deterministic fake provider plus LiteLLM and LM Studio Responses adapters
- `ProviderRuntime` as the only approved provider construction boundary
- Core `TurnOrchestrator` for the existing provider-foundation turn path
- one-shot CLI provider path and manual provider smoke harness
- minimal telemetry lifecycle through `TelemetrySink`, `NoopTelemetrySink`, and
  `make_trace_event(...)`

Process Readiness has started:

- `HealthCheck` and `VersionInfo` contracts exist
- local `ProcessRuntime` health/version object construction exists
- ProcessRuntime boundary gate completed
- CLI health/version commands exist
- local health/version API app object exists for `GET /health` and
  `GET /version` only
- manual local health/version runner exists for developer smoke on
  `127.0.0.1:8765`
- local bearer-token auth helper protects `/v1/turns`
- protected `/v1/turns` adapter exists with an injected handler boundary only
- RuntimeComposition provides a fake-provider-only handler factory for the
  injected local API handler boundary
- RuntimeComposition provides a developer-only fake `/v1/turns` manual smoke
  runner that composes that handler with the local API runner
- the developer-only fake `/v1/turns` manual smoke has been executed and
  recorded with bounded safe output details
- the future trace exposure decision is recorded: current-process, in-memory,
  telemetry-owned reader/store, injected into Local API, protected by bearer auth
- protected `GET /v1/traces/{trace_id}` now reads only from an explicitly
  injected current-process in-memory telemetry reader
- local service startup foundation can now generate a local bearer token and
  safe startup metadata without starting a service or writing discovery files
- local service startup can now run a narrow Local API service-runner startup
  proof that injects the generated token into the existing Local API runner and
  prints safe metadata only
- local service startup can now write safe local-user-scoped discovery metadata
  without raw tokens, remote bind addresses, provider credentials, or handler
  configuration
- the Local API service-runner startup proof can now explicitly write that safe
  discovery metadata through `--discovery-file <path>` while still passing the
  raw generated token only to the Local API runner call
- a narrow future Shell/CLI client helper can now load safe discovery metadata
  and make explicit loopback JSON calls while requiring per-call bearer token
  input for protected turn and trace endpoints
- the developer-only fake `/v1/turns` runner now injects one current-process
  reader/sink so the same process can read the fake turn trace by `trace_id`
- the fake `/v1/turns` plus protected trace-read manual smoke has been executed
  and recorded with bounded safe output details
- no real-provider turn execution composition, service daemon, subprocess
  runtime, or service mode exists
- telemetry now has explicit local NDJSON persistence, while cross-process
  lookup, trace search, trace streaming, service daemon behavior, and default
  product sink wiring remain blocked

Assistant-runtime foundation now present:

- approved assistant-envelope models: `InputEvent`, `AssistantTurnInput`,
  `AssistantTurnResult`, and `AssistantFinalResponse`
- assistant-runtime input normalization, result assembly, no-provider runtime
  skeleton, structured-output consumption helpers, and provider-stage skeleton
- Core internal assistant-runtime provider-stage wiring skeleton
- official explicit CLI fake-provider foundation mode via
  `--assistant-runtime-fake-provider`; the Task 107 flag
  `--assistant-runtime-provider-stage-fake` remains a compatibility alias
- CLI now calls RuntimeComposition for both the official fake-provider
  AssistantRuntime foundation mode and the existing provider-foundation turn
  path; CLI no longer imports ProviderRuntime directly
- ProviderRuntime production bridge ownership decision: future real-provider
  AssistantRuntime composition belongs in a separate runtime composition/factory
  layer, not in CLI, Core, AssistantRuntime, ProviderRuntime, ports, or adapters
- `packages.runtime_composition.run_fake_provider_assistant_bridge(...)` proves
  that separate layer with ProviderRuntime-created fake provider only; it calls
  Core's assistant-provider-stage helper and reaches AssistantRuntime provider
  stage behavior without changing default CLI behavior
- `packages.runtime_composition.run_lmstudio_responses_assistant_bridge(...)`
  is the first explicit real-provider-backed AssistantRuntime proof path
- explicit non-default CLI proof mode via
  `--assistant-runtime-lmstudio-responses`; it calls RuntimeComposition and is
  not default, service/API, or product flow
- documented manual live-smoke checklist and bounded failure policy for LM
  Studio unavailable/model rejected, timeout-like, provider error, empty output,
  and malformed response cases
- recorded successful manual live smoke for `qwen3.5-0.8b`, with bounded output
  details and no CI/live-provider validation requirement

Provider structured-output foundation now present:

- boundary-local validation and fallback result model
- adapter-local hooks for LM Studio Responses and LiteLLM
- explicit ProviderRuntime experimental structured-output adapter call path
- internal handoff draft and pressure coverage
- test-only ProviderRuntime-to-AssistantRuntime bridge proof
- no production structured-output bridge or product runtime integration

Validation gates now present:

- workspace/docs/service-placeholder/forbidden-module gates
- project status, file-size, schema-version, library-decision, and library
  research gates
- port, ProviderRuntime, ProcessRuntime, AssistantRuntime, provider structured
  output, runtime composition, local API, local API client, runtime ownership,
  Vaxil boundary, and assistant-turn contract gates

Historical governance retained compactly: Task 024 Status and README Drift Cleanup,
Git workflow governance, assistant-turn spine/contract governance, runtime
ownership governance, and library research governance remain accepted.

## Task 102-130 Compact Milestone Summary

Detailed Task 102-131 history is retained in git history and package docs.

<!-- file size justification: PROJECT_STATUS.md intentionally stays just over
500 lines while the current multi-foundation status remains compacted in place;
future status cleanups should move older milestone detail to dedicated docs. -->

- Task 102 wired telemetry-owned structured-output trace safety into
  `packages.telemetry.sinks.make_trace_event(...)`.
- Task 103 added explicit AssistantRuntime structured-output consumption as an
  experimental helper.
- Task 104 proved ProviderRuntime structured-output output can be consumed by
  AssistantRuntime only through test/integration helpers.
- Task 105 added `run_provider_stage_turn(...)`, an AssistantRuntime-owned
  injected provider-stage skeleton.
- Task 106 added `run_assistant_provider_stage_turn(...)`, a Core-owned
  internal wiring skeleton that delegates to AssistantRuntime.
- Task 107 added the opt-in CLI/dev fake-provider vertical slice with
  `--assistant-runtime-provider-stage-fake`, leaving default CLI behavior
  unchanged.
- Task 108 compacted this status file and recorded the next runtime promotion
  decision.
- Task 109 promoted the explicit fake-provider AssistantRuntime CLI path into
  the official foundation mode `--assistant-runtime-fake-provider` while keeping
  the Task 107 flag as a compatibility alias.
- Task 110 decides that a future separate runtime composition/factory layer
  should own production composition between ProviderRuntime and the
  Core/AssistantRuntime assistant-provider-stage path.
- Task 111 adds that first separate layer as a fake-provider-only proof with a
  dedicated runtime composition boundary gate.
- Task 112 wires the official CLI fake-provider foundation mode to the
  RuntimeComposition fake bridge and removes CLI-owned provider construction
  while preserving default CLI behavior.
- Task 113 adds the first RuntimeComposition real-provider proof for
  `lmstudio_responses`, with live execution left to manual provider smoke
  guidance only.
- Task 114 adds the explicit non-default CLI proof flag
  `--assistant-runtime-lmstudio-responses` for that bridge while preserving
  default CLI behavior and the fake-provider foundation mode.
- Task 115 documents manual live-smoke expectations and failure policy for that
  proof mode without adding preflight, routing, retry/fallback, sessions/history,
  model-selection, service/API, or default product behavior.
- Task 116 records a successful manual LM Studio AssistantRuntime CLI proof
  smoke and adds narrow Unicode-safe result printing for that proof-mode output.
- Task 117 adds local health/version API readiness as a dependency-free WSGI app
  object for `GET /health` and `GET /version` only, with a dedicated boundary
  gate and no service listener or turn/provider execution.
- Task 118 adds a manual standard-library loopback runner for that health/version
  app object and smoke documentation, while keeping live server execution out of
  CI and avoiding `/v1/turns`, provider execution, service daemon behavior, or
  product runtime behavior.
- Task 119 classifies health/version as public loopback readiness endpoints and
  future turn/trace/event endpoints as protected. It adds a reusable local
  bearer-token validator for future protected endpoints without wiring auth to
  current health/version behavior or implementing protected endpoints.
- Task 120 decides the protected `/v1/turns` contract, owner split, auth
  enforcement, fake-provider-only first target, response/error behavior, and
  rollback path without implementing the endpoint or adding API execution.
- Task 121 implements the protected fake-provider-only `/v1/turns` adapter with
  auth-before-body validation and stubbed-handler tests only, without adding
  real execution composition.
- Task 122 adds RuntimeComposition-owned fake handler composition for local API
  turns, without making local API import RuntimeComposition or adding LM Studio
  or real-provider API execution.
- Task 123 adds a RuntimeComposition-owned developer-only manual fake
  `/v1/turns` smoke runner with a caller-provided fake/dev token, while keeping
  local API free of RuntimeComposition imports.
- Task 125 records a successful developer-only fake `/v1/turns` manual smoke:
  health/version responded, a valid protected fake turn returned
  `AssistantTurnResult`, auth failures returned safe `AUTH_REQUIRED`, and no
  runtime behavior changed.
- Task 126 decides the future trace exposure path: protected
  `GET /v1/traces/{trace_id}`, local API envelope, telemetry-owned
  current-process in-memory reader/store, no raw trace objects, no persistence,
  and no implementation in this task.
- Task 127 implements the protected fake/local-only trace-read path using
  `packages.telemetry.InMemoryTraceReader` and local API reader injection. The
  endpoint returns safe projection envelopes only; raw `TraceEvent.data`,
  provider payloads, provider response ids, auth material, and secrets are not
  exposed.
- Task 128 integrates fake-turn trace recording only for the manual/dev local
  API fake path. RuntimeComposition passes the injected sink through existing
  fake-provider bridge telemetry, while Local API continues to receive only
  injected handler/reader callables.
- Task 129 records successful manual fake local API turn plus protected trace
  read smoke, with safe current-process trace projections only.
- Task 130 decides that the next real-provider local API step should be an
  explicit LM Studio Responses manual/dev mode only, not a generic provider API
  or service daemon.
- Task 131 adds that explicit manual/dev LM Studio Responses local API runner
  and handler while preserving fake mode and local API boundaries.

## Architecture Health Notes

- The current direction is still foundation-first rather than product-first.
- Telemetry owns redaction/sanitization policy; callers use safe event
  construction instead of owning sanitizer policy.
- Future trace reads must remain telemetry-owned for recording/lookup/safety and
  Local API-owned only for auth/HTTP/JSON adapter behavior.
- AssistantRuntime remains provider-agnostic and does not import Core,
  ProviderRuntime, adapters, ports, CLI, or services.
- Core has a narrow assistant-runtime provider-stage seam but the existing
  `TurnOrchestrator` provider path remains unchanged.
- CLI has one explicit fake-provider AssistantRuntime foundation mode and one
  explicit LM Studio Responses AssistantRuntime proof mode. Both call
  RuntimeComposition; the default provider CLI path remains the
  provider-foundation path and still does not construct providers inside CLI.
- The LM Studio Responses CLI proof has documented manual-smoke success/failure
  expectations; automated validation still does not require live LM Studio.
- The latest manual smoke for that proof path succeeded, but it remains a
  manual developer check and is not part of `run_all_checks.py`.
- Local service readiness now has a health/version API app object and a manual
  loopback runner only. It is not a service daemon.
- Local API auth policy protects `/v1/turns`; health/version behavior remains
  public and unchanged.
- Local API auth policy also protects `GET /v1/traces/{trace_id}` when a trace
  reader is explicitly injected.
- The `/v1/turns` adapter is protected fake-provider-only by request envelope:
  it accepts a local envelope carrying `AssistantTurnInput`, returns
  `AssistantTurnResult`, and delegates only to an injected handler.
- RuntimeComposition now owns the fake injected handler factory for local API
  turns and routes it through the existing fake-provider bridge path.
- RuntimeComposition also owns the developer-only fake-turns smoke runner that
  injects that handler into the local API runner. Its manual fake smoke has
  been recorded, and it now shares an in-memory trace reader between fake turn
  recording and protected trace reads. It is not a service daemon or production
  token lifecycle.
- ProviderRuntime remains the only approved production provider construction
  boundary. RuntimeComposition may call it for approved bridge proofs while
  importing no concrete adapters and owning no routing/session/history policy.
- RuntimeComposition is now the approved CLI composition dependency for the
  existing provider-foundation path and the fake-provider AssistantRuntime
  foundation mode. Core, AssistantRuntime, and ProviderRuntime still do not
  import RuntimeComposition.
- RuntimeComposition also owns one real-provider AssistantRuntime proof function
  for `lmstudio_responses`, now reachable from an explicit CLI proof flag. It
  is not a router, session manager, retry/fallback owner, model-selection owner,
  API-key policy owner, or product orchestrator.
- Task 130 unlocks only a future explicit LM Studio Responses local API
  implementation pack; it does not itself implement real-provider `/v1/turns`.
- Task 131 implements only that explicit developer runner/handler path; it is
  not default, generic provider routing, model selection, preflight enforcement,
  retry/fallback, session/history, or service daemon behavior.
- `PROJECT_STATUS.md` is no longer a chronological task log; historical detail
  belongs in package READMEs, tests, task reports, and git history.

## Explicit Non-Goals And Blocked Work

Blocked without a separate approved task spec:

- default CLI behavior changes
- ProviderRuntime production bridge into AssistantRuntime
- real provider promotion for assistant-runtime turns
- Core normal orchestration replacement
- service/API/HTTP/WebSocket/subprocess runtime or daemon behavior
- real-provider execution composition behind `/v1/turns` beyond the explicit
  Task 131 developer-only LM Studio Responses runner/handler path
- generic provider local API mode and any non-LM-Studio first provider mode
- telemetry cross-process trace storage, trace search, trace streaming, default
  product sink wiring, and non-local persistence backends
- contract or port promotion
- tools, UI, voice, desktop, vision, proactive behavior
- embeddings, vector search, automatic transcript extraction, raw transcript
  persistence, product memory integration, or memory backend promotion
- hidden history, routing, retry/fallback, API keys, or model routing
- structured-output handoff promotion into a public contract

A roadmap item, package README note, status recommendation, or task number is
not implementation permission.

## Next Implementation Task

The recommended next major foundation is an Assistant Policy And Permission
Readiness Foundation. It should define safe policy decision/readiness primitives
and permission-flow references for future assistant stages without implementing
tools, UI, voice, desktop, vision, proactive behavior, service daemon behavior,
generic provider API mode, routing, retry/fallback, model selection, API-key
policy execution, WebSocket/event streams, cross-process trace lookup, raw
transcript persistence, memory backend promotion, automatic memory extraction,
or default CLI changes.

## Capability Platform Foundation

Capability Platform Foundation is complete as a foundation slice. It adds `packages/capability_runtime`, adapter seams under `packages/adapters/capabilities`, safe lifecycle summary linkage in AssistantRuntime, deterministic fake capability proof tests, dependency/adoption documentation, and the `check_capability_runtime_boundaries.py` validation gate.

Complete:

- CapabilityRuntime central models for refs, manifests, permissions, approval, eligibility, context delivery, compaction, proposals, execution requests, result/error envelopes, summaries, loop guards, planning readiness, verification hooks, and safe projections.
- Adapter seams for MCP, OpenAI tools/Agents SDK shape, LiteLLM gateway/toolset metadata, LM Studio tool/MCP host proposals, skills, plugins, connectors, integrations, and harness/context delivery concepts.
- Safe deterministic fake capability proof: permission -> dispatch -> result -> safe summary, with no shell, filesystem, network, browser, OS, or raw payload persistence.
- AssistantRuntime lifecycle can reference safe capability readiness/result counts without dispatching capabilities.
- Boundary validation blocks ownership drift and adapter policy bypass.

Blocked/deferred:

- Official MCP SDK is not added yet because this phase does not introduce real MCP protocol mechanics, arbitrary server execution, registry install, or real tool calls. It remains the required SDK when real MCP protocol code is introduced.
- OpenAI Agents SDK, LangGraph/LangChain, LlamaIndex, Claude Skills runtime behavior, and external account connectors remain reference/adaptor-seam only until separate approved tasks.

Recommended next:

- Add a no-network provider tool-call proposal fixture that maps provider-native tool proposals into CapabilityRuntime proposals without execution.
- Add an approved MCP SDK spike only when Marvex is ready for a disabled real client listing proof with explicit local allowlists.
