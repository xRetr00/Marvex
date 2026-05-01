# Contract Approvals

This registry controls whether a documented contract may be used for implementation.

`docs/CONTRACTS.md` describes intended contract shapes. A contract is not implementation-approved until this registry says `approval_status: approved` and `implementation_allowed: yes`.

The current approved contracts are provider-foundation contracts, not
assistant-turn contracts. Task 043B does not approve any assistant-level
contracts.

Draft assistant-envelope contracts may be listed here with
`approval_status: draft` and `implementation_allowed: no`. That listing is
documentation only and does not approve implementation.

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
| InputEvent | 0.1.1-draft | draft | none | none | no |
| AssistantTurnInput | 0.1.1-draft | draft | none | none | no |
| AssistantTurnResult | 0.1.1-draft | draft | none | none | no |
| AssistantFinalResponse | 0.1.1-draft | draft | none | none | no |
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
