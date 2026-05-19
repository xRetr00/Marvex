# Project Status

current_phase: adaptive_context_evidence_memory_learning_governance_complete

implementation_status: adaptive_context_evidence_memory_learning_governance_complete

accepted_docs: true

current_governance_gate:
Adaptive Context, Evidence, Memory Learning, and Governance Completion

Previous cleanup phase: `governance_reconciliation_boundary_hardening_complete`.

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

The memory tree follow-up audit closed in-boundary gaps without adding live connector sync. Evidence links now flow through safe tree projections, scoring projections include component explanations, SQLite tree index readbacks include evidence metadata, source forget deletes indexed documents/chunks/scores/tree nodes, and Control Plane web exposes source tree, topic tree, daily digest, evidence drill-down, source forget, and auto-fetch controls. Live OAuth sync, background schedules, and broad account actions remain blocked future work.

## Assistant Intelligence and Tool-Using Runtime Integration Checkpoint

Marvex now has a bounded deeper tool-using assistant turn path. IntentRuntime can use deterministic routing or an injected semantic-router-backed adapter result while still owning Marvex intent decisions. ContextRuntime and PromptHarnessRuntime select only route-relevant safe context, including Memory Tree evidence refs/counts for memory-tree-needed turns. Provider tool calls remain proposals; CapabilityRuntime remains the only owner of approval, execution requests, result envelopes, and dispatch policy. The integration includes the safe browser workflow, allowlisted MCP live proof path, approval resume/deny/cancel state, provider continuation readiness, trace-searchable safe telemetry summaries, and Control Plane-safe counts/status projections.

Still blocked: generic provider routing/model selection, retry/fallback policy, direct browser-use execution, arbitrary browser/computer actions, arbitrary MCP server launch/install, shell/filesystem tools, live OAuth/account sync, hidden auto-fetch, raw transcript/prompt/tool/provider/browser payload persistence, voice, Orb/Face UI, desktop overlay, and proactive behavior.


## Provider Tool Continuation and Live Execution Hardening Checkpoint

Marvex now has a bounded provider tool continuation path for safe built-in execution. LM Studio/OpenAI-compatible provider tool calls are normalized as proposals, malformed arguments are denied without fallback execution, safe calculator results become provider continuation input summaries, and final fake-provider continuation responses are represented without persisting raw provider payloads or raw tool arguments.

Approval resume now distinguishes approved, denied, and cancelled outcomes in safe projections. Approved Playwright-backed browser navigation can execute after CapabilityRuntime approval when a page boundary is supplied; click/type remain approval-gated and no browser-use execution was promoted. Trace search and Control Plane summaries expose only counts/status booleans for proposal, approval, execution, continuation, and final response state.

## Real Tool-Using Assistant Runtime Completion Checkpoint

Marvex now has a narrow real provider continuation handoff path: provider tool calls from OpenAI-compatible, LM Studio, or LiteLLM-shaped payloads map into Marvex-owned proposals, unsafe tool names are denied instead of normalized into executable actions, safe built-in execution remains CapabilityRuntime-owned, and an injected ProviderPort-compatible continuation adapter receives only safe continuation summaries before producing the final assistant response. The default no-provider test path remains an explicit fake-provider proof rather than generic provider routing.

Browser-use moved beyond import-only to a controlled adapter proof that exposes allowed browser-agent categories and the exact direct-execution blocker, while Playwright remains the real low-level SDK-backed browser path. Control Plane now exposes a Runtime Execution view and `/control/runtime/execution` safe projection for provider proposals, pending approvals, tool/browser/MCP status, provider continuation, final response readiness, bounded loop guards, risk level, and safe trace refs. Frontend views display and approval-state data only; they do not execute tools.

Still blocked after this checkpoint: live provider credential smoke as a required automated test, generic provider routing/model selection, retry/fallback policy, direct Browser-use SDK execution, arbitrary browser/computer actions, arbitrary MCP server launch/install, shell/filesystem tools, live OAuth/account sync, hidden auto-fetch, raw transcript/prompt/tool/provider/browser payload persistence, voice, Orb/Face UI, desktop overlay, and proactive behavior. The next recommended goal is Voice Runtime Foundation because the remaining proof-only runtime/tooling items are bounded adapter limitations, not blockers for voice contracts.


## Hybrid Intent, Web Search, Grounded Evidence, and Risk-Based Governance Checkpoint

Marvex now has a real hybrid intent path for pre-Voice runtime use. `semantic-router[hybrid]==0.1.14` is declared and uv-resolved, with the exact uv result that this version has no `hybrid` extra; Marvex therefore uses real local `semantic_router.Route` definitions plus Marvex-owned hybrid fallback logic. `llama-index-core>=0.14.22` is adopted narrowly for selector proof through `SingleSelection`; LlamaIndex does not own Core, RuntimeComposition, MemoryRuntime, prompt assembly, or agent planning.

`packages.web_search_runtime` adds SearXNG HTTP/JSON search and DDGS fallback adapters with safe web result/evidence models. SearXNG is preferred when configured; DDGS uses the real `ddgs>=9.14.4` package behind the adapter. `packages.grounded_answer_runtime` validates that grounded answer citations map to web evidence refs before acceptance, and PromptHarnessRuntime can receive bounded web evidence context through `ContextSourceKind.WEB_SEARCH_EVIDENCE`.

Risk governance now allows read/list/search/inspect/summarize by default, requires approval for write/delete/send/upload/install/run/connect/private-account actions, and reserves hard-block for malware, credential theft, injection exploitation, exfiltration, unauthorized account abuse, CAPTCHA/anti-bot bypass, stealth abuse, destructive/payment actions without consent, and policy override attempts.

Still blocked after this checkpoint: Voice runtime, Orb/Face UI, desktop overlay, proactive behavior, arbitrary tool execution, arbitrary MCP install/execute, broad OAuth sync, hidden auto-fetch, raw provider/tool/browser/search payload persistence, browser side effects without approval, and generic provider routing/model selection. Voice Runtime Foundation can start next if final validation stays green because the remaining search/governance boundaries are bounded and tested.


## Adaptive Context, Evidence, Memory Learning, and Governance Checkpoint

Marvex now has route-adaptive prompt/context delivery before Voice. Grounded lookup routes get non-zero evidence budget, citation guidance, and web evidence sections. Memory routes get non-zero memory budget and memory evidence sections. Tool, browser, and MCP routes get eligible capability schema sections plus approval policy context. Clarification routes stay concise and suppress unnecessary blocks intentionally rather than accidentally.

Memory Tree search now has a local semantic/filterable search path with deterministic token-vector scoring, synonym normalization, metadata/hotness ranking, and filters for trust level, recency, entity, topic, source, source type, hotness, and evidence availability. No new embedding dependency was added; `fastembed` or `sentence-transformers` remain future options only if a later goal proves local embeddings are needed.

LearningRuntime now records safe feedback events and produces review-required memory, skill, policy, preference, route-example, and memory-hotness candidates from corrections, ratings, tool outcomes, memory-use feedback, and intent/retrieval failures. It cannot silently mutate skills or policy.

Governance now has granular, reason-coded audit decisions for allow, approval_required, deny, quarantine, and hard_block. MCP allowlist state can be projected from runtime/config/control-plane policy and changes are review-required proposals, not silent source-only mutation.

Still blocked after this checkpoint: Voice runtime, Orb/Face UI, desktop overlay, proactive behavior, arbitrary tool execution without approval, broad live OAuth sync, hidden auto-fetch, silent policy/skill mutation, raw sensitive payload persistence, generic provider routing/model selection, and paid/cloud-only embeddings. Voice Runtime Foundation can start next if final validation remains green.

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

Bounded foundations: assistant turn integration, telemetry, Local API, Control Plane API, Control Plane web, CapabilityRuntime, tool execution foundations, MCP adapter, MemoryRuntime, MarketplaceRuntime, SessionRuntime, IntentRuntime, ContextRuntime, and PromptHarnessRuntime. These foundations may be maintained and tested, but expansion is blocked unless a future goal updates `docs/CONTRACT_APPROVALS.md`, this status file, validation gates, and relevant architecture docs.

Experimental seams: browser/computer-use adapter seams are present for policy-gated proposals and bounded adapter proofs only. They are not general product permission for browser or desktop automation.

Future service contracts: `services/*` placeholders remain README-only. Voice, desktop agent, shell/orb UI, proactive behavior, and vision remain forbidden product behavior for now.

## Cleanup Result

This governance cleanup hardened the repository around two current risks:

- `packages/capability_runtime/execution.py` must stay a re-export facade, with execution models split into focused CapabilityRuntime modules.
- `packages/assistant_turn_integration/spine.py` must stay a narrow composition spine, with stage logic extracted into focused assistant turn integration modules.

CapabilityRuntime remains authoritative for permissions, approvals, execution requests, result envelopes, and loop guards. Assistant turn integration coordinates approved runtime layers but must not become the assistant brain. Core remains orchestration-only. ProviderRuntime remains provider construction only. Local API and Control Plane remain HTTP/auth/JSON and safe projection layers only.

## Blocked

Blocked without explicit future approval: new product features, new dependencies, generic provider routing/model selection, arbitrary tool execution, shell execution, filesystem write/edit/delete tools, arbitrary MCP install/launch/execute, arbitrary skill install/remote loading/script execution, uncontrolled browser/computer/desktop automation, raw prompt/transcript/tool/provider/browser payload persistence by default, voice, Orb, desktop overlay, proactive behavior, and vision.

## Next Recommended Goal

Voice Runtime Foundation can start next, provided it keeps voice behind explicit contracts and does not widen provider routing, tool execution, browser automation, OAuth sync, learning mutation, or raw payload persistence.

Browser-use backend remains disabled for direct SDK execution; the controlled adapter proof exposes only safe status, allowed categories, and blocker metadata.
