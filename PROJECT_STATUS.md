# Project Status

current_phase: governance_reconciliation_boundary_hardening_complete

implementation_status: governance_reconciliation_boundary_hardening_complete

accepted_docs: true

current_governance_gate:
Governance Reconciliation, Boundary Hardening, and Sprawl Cleanup

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

Still blocked: generic provider routing/model selection, retry/fallback policy, browser-use execution, arbitrary browser/computer actions, arbitrary MCP server launch/install, shell/filesystem tools, live OAuth/account sync, hidden auto-fetch, raw transcript/prompt/tool/provider/browser payload persistence, voice, Orb/Face UI, desktop overlay, and proactive behavior.

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

Foundation cleanup checkpoint: continue reducing large-file and central-brain risk inside bounded foundations without adding product features. Start with focused ownership splits, boundary tests, and docs/gates updates for any remaining files that approach god-object size or mix policy with adapter mechanics.
