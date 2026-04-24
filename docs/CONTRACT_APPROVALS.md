# Contract Approvals

This registry controls whether a documented contract may be used for implementation.

`docs/CONTRACTS.md` describes intended contract shapes. A contract is not implementation-approved until this registry says `approval_status: approved` and `implementation_allowed: yes`.

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
| TurnInput | 0.1-draft | draft | none | none | no |
| TurnOutput | 0.1-draft | draft | none | none | no |
| FinalResponse | 0.1-draft | draft | none | none | no |
| ProviderRequest | 0.1-draft | draft | none | none | no |
| ProviderResponse | 0.1-draft | draft | none | none | no |
| TraceEvent | 0.1-draft | draft | none | none | no |
| ErrorEnvelope | 0.1-draft | draft | none | none | no |
| HealthCheck | 0.1-draft | draft | none | none | no |
| VersionInfo | 0.1-draft | draft | none | none | no |
| CoreService | 0.1-draft | draft | none | none | no |
| ProviderWorker | 0.1-draft | draft | none | none | no |
| ToolWorker | 0.1-draft | draft | none | none | no |
| IntentWorker | 0.1-draft | draft | none | none | no |
| VoiceWorker | 0.1-draft | draft | none | none | no |
| DesktopAgent | 0.1-draft | draft | none | none | no |
| Shell | 0.1-draft | draft | none | none | no |

## Approval Rules

- Approval changes require an updated task spec and final report.
- `schema_version` must change when compatibility is broken.
- `approval_status: approved` is invalid without an approver and approval date.
- `implementation_allowed: yes` is invalid unless approval status is `approved`.
- Service placeholder folders remain README-only until their matching service contract has `implementation_allowed: yes`.
