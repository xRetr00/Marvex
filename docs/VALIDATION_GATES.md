# Validation Gates

Validation gates are mandatory before finishing any task, including a one-line hotfix.

## Required Command

```powershell
python scripts/run_all_checks.py
```

## Gates

### Docs Accepted Gate

Implementation is blocked while `PROJECT_STATUS.md` has `accepted_docs: false`. The only allowed source files in that state are governance validation scripts under `scripts/`.

### Workspace Policy Gate

Expected folders and required documents must exist.

### Service Placeholder Gate

Every `services/*` folder must remain README-only until its service contract is approved in `docs/CONTRACT_APPROVALS.md` and `implementation_allowed` is `yes`.

### Forbidden Modules Gate

V1-forbidden modules must not appear as implementation directories.

### File Size Gate

No non-doc file may exceed 500 lines without explicit justification.

### Vaxil Boundary Gate

Vaxil may be mentioned only as a cautionary research source. Code reuse language and imports are forbidden.

### Library Decision Gate

Dependency recommendations must include official source, maintenance status, why use it, why not custom code, and fallback if abandoned.

### Task Spec Gate

Every implementation task requires a real task spec file. A task id alone is not sufficient.

The task spec must define goal, allowed files, forbidden files, contract impact, ownership boundary, tests required, validation commands, rollback plan, and final report format.

### Contract Approval Gate

Implementation may use only contracts listed in `docs/CONTRACT_APPROVALS.md` with approval status `approved` and `implementation_allowed` set to `yes`.
