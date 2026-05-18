# Contract Approvals

This registry controls whether a documented contract may be used for implementation.

`docs/CONTRACTS.md` describes intended contract shapes. A contract is not implementation-approved until this registry says `approval_status: approved` and `implementation_allowed: yes`.

The current approved contracts include provider-foundation contracts and the
smallest assistant envelope contracts. Provider-foundation contracts are still
not full assistant-turn contracts.

The approved assistant-envelope contracts may be used by future implementation
tasks, but approval does not implement Pydantic models, runtime behavior, Core
behavior, CLI behavior, ProviderRuntime behavior, tools, memory, voice, UI,
desktop, proactive behavior, HTTP, IPC, or service runtime.

## Approval Fields

- `contract_name`: Stable contract or service contract name.
- `schema_version`: Contract schema version.
- `approval_status`: `draft`, `approved`, `deprecated`, or `blocked`.
- `approver`: Human or review authority that approved the contract. Use `none` while draft.
- `approval_date`: ISO date, or `none` while draft.
- `implementation_allowed`: `yes` or `no`.

## Current Registry

| contract_name | schema_version | approval_status | approver | approval_date | implementation_allowed |
| --- | --- | --- | --- | --- | --- |
| TurnInput | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| TurnOutput | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| FinalResponse | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| ProviderRequest | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| ProviderResponse | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| TraceEvent | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| ErrorEnvelope | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| HealthCheck | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| VersionInfo | 0.1.1-draft | approved | user | 2026-04-24 | yes |
| InputEvent | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| AssistantTurnInput | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| AssistantTurnResult | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| AssistantFinalResponse | 0.1.1-draft | approved | user | 2026-05-01 | yes |
| CoreService | 0.1.1-draft | draft | none | none | no |
| ProviderWorker | 0.1.1-draft | draft | none | none | no |
| ToolWorker | 0.1.1-draft | draft | none | none | no |
| IntentWorker | 0.1.1-draft | draft | none | none | no |
| VoiceWorker | 0.1.1-draft | draft | none | none | no |
| DesktopAgent | 0.1.1-draft | draft | none | none | no |
| Shell | 0.1.1-draft | draft | none | none | no |

## Approval Rules

- Approval changes require an updated task spec and final report.
- `schema_version` must change when compatibility is broken.
- `approval_status: approved` is invalid without an approver and approval date.
- `implementation_allowed: yes` is invalid unless approval status is `approved`.
- Service placeholder folders remain README-only until their matching service contract has `implementation_allowed: yes`.

## Implementation Surface Classification Rule

Existing code is not approval. Future work is allowed only when supported by the current goal spec, `docs/CONTRACT_APPROVALS.md`, `PROJECT_STATUS.md`, validation gates, and relevant architecture docs.

`docs/GOVERNANCE_CLASSIFICATION.md` is the current registry for implemented and future surfaces. The registry distinguishes approved implementation surfaces, bounded foundations, experimental seams, future service contracts, and forbidden product behavior for now.

Existing bounded foundations may be maintained, tested, and safely refactored inside their current boundaries. They must not expand into product behavior unless this approval registry, project status, validation gates, and architecture docs are updated by an explicit future goal.

## Current Surface Summary

- provider foundation: approved implementation surface for provider-foundation scope only.
- assistant turn contracts: approved implementation surface only for approved assistant envelope contracts.
- assistant turn integration: bounded foundation; expansion blocked without explicit approval.
- telemetry: bounded foundation; safe summaries/persistence only.
- local api: bounded foundation; HTTP/auth/JSON only.
- control plane api: bounded foundation; safe projections and approval APIs only.
- control plane web: bounded foundation; isolated local admin dashboard only.
- capability runtime: bounded foundation; policy/approval/dispatch/result envelopes only.
- tool execution foundations: bounded foundation; approved safe requests only.
- mcp adapter/seam: bounded foundation; official SDK and allowlist only.
- browser/computer-use adapter/seam: experimental seam; product automation blocked.
- memory runtime: bounded foundation; safe refs/backend only.
- marketplace runtime: bounded foundation; read-only metadata/proposals only.
- session runtime: bounded foundation; safe refs only.
- intent/prompt harness seams: bounded foundation; safe projections and bounded prompt plans only.
- service placeholders: future service contract; README-only.
- future voice, desktop agent, shell/orb UI, proactive behavior, and vision: forbidden product behavior for now.
