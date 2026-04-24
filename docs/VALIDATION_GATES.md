# Validation Gates

Validation gates are mandatory before finishing any task, including a one-line hotfix.

## Required Command

```powershell
python scripts/run_all_checks.py
```

## Gates

### Docs Accepted Gate

Implementation is blocked while `PROJECT_STATUS.md` has `accepted_docs: false`.

### Workspace Policy Gate

Expected folders and required documents must exist.

### Service Placeholder Gate

Every `services/*` folder must remain README-only until its contract is approved.

### Forbidden Modules Gate

V1-forbidden modules must not appear as implementation directories.

### File Size Gate

No non-doc file may exceed 500 lines without explicit justification.

### Vaxil Boundary Gate

Vaxil may be mentioned only as a cautionary research source. Code reuse language and imports are forbidden.

### Library Decision Gate

Dependency recommendations must include official source, maintenance status, why use it, why not custom code, and fallback if abandoned.

### Task Spec Gate

Implementation tasks require a task spec or documented task id.

