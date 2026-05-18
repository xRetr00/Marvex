# Project Status

current_phase: governance_reconciliation_boundary_hardening_complete

implementation_status: governance_reconciliation_boundary_hardening_complete

accepted_docs: true

current_governance_gate:
Governance Reconciliation, Boundary Hardening, and Sprawl Cleanup

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
