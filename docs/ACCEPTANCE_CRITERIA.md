# Acceptance Criteria

## Bootstrap Acceptance

The bootstrap is complete only when:

- the Marvex folder exists
- all required docs exist
- all templates exist
- all placeholder service folders are README-only except explicitly approved
  service-owned entrypoint files such as `services/core/main.py`
- validation scripts exist
- `python scripts/run_all_checks.py` passes
- no product implementation exists
- no legacy code is copied or reused
- `PROJECT_STATUS.md` says `accepted_docs: false` until the user explicitly accepts the blocker fixes
- contract approval status is documented in `docs/CONTRACT_APPROVALS.md`
- implementation tasks require real task spec files, not task ids alone
- future agents can understand exactly what is allowed before implementation

## V1 Foundation Acceptance

After docs are accepted and implementation begins, v1 foundation is correct only when:

- CLI sends text
- Core calls provider through interface
- telemetry logs trace_id
- previous_response_id is supported
- no provider-specific code exists in Core
- fake provider tests pass
- LM Studio payload tests pass

V1 implementation may not start while `PROJECT_STATUS.md` has `accepted_docs: false`.
