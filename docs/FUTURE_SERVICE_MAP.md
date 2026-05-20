# Future Service Map

This document is a concise index of future Assistant OS service boundaries.
It is not an approval registry. `docs/CONTRACT_APPROVALS.md` remains the source
of truth for whether a contract may be implemented.

## Future Boundaries

| Service | Purpose | Approval state |
| --- | --- | --- |
| MemoryService | Durable memory ingestion, lookup, retrieval, and safe memory projections | draft/no implementation |
| TelemetryEventService | Persistent event history, safe trace/event ingestion, and audit-friendly readback | draft/no implementation |
| PolicyPermissionService | Policy evaluation, permission decisions, approval state, and safe runtime policy projections | draft/no implementation |

## Notes

- These boundaries are future service contracts only.
- Current package foundations remain bounded in-process until approval changes.
- Do not treat this map as implementation permission.
