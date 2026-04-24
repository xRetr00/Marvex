# Acceptance Criteria

## Bootstrap Acceptance

The bootstrap is complete only when:

- the Marvex folder exists
- all required docs exist
- all templates exist
- all placeholder service folders are README-only
- validation scripts exist
- `python scripts/run_all_checks.py` passes
- no product implementation exists
- no legacy code is copied or reused
- `PROJECT_STATUS.md` says docs are not accepted yet
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

