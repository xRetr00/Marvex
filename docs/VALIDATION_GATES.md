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

### Port Boundary Gate

Port files are interface contracts only.

- Port contract files over 120 lines fail unless explicitly justified.
- Port contract files mentioning concrete implementation names fail.
- Adapter files importing Core fail.
- Core files importing adapters fail.
- Registry and factory files over 250 lines require split or explicit justification.

### ProviderRuntime Boundary Gate

ProviderRuntime is the only boundary allowed to import approved concrete provider adapters.

- Core must not import ProviderRuntime or adapters.
- CLI must not import concrete provider adapters.
- ProviderPort must not mention concrete provider names.
- ProviderRuntime may import only approved provider adapters.
- ProviderRuntime must not contain routing, fallback, retry, session, history, plugin, daemon, server, health routing, or model routing logic.
- Strict runtime scans target Python source files only, not README files.

### Vaxil Boundary Gate

Vaxil may be mentioned only as a cautionary research source. Code reuse language and imports are forbidden.

### Library Decision Gate

Dependency recommendations must include official source, maintenance status, why use it, why not custom code, and fallback if abandoned.

Runtime dependencies listed in `[project].dependencies` must have matching
decision records under `docs/library-decisions/` with `pyproject dependency`
and `declared dependency` fields.

### Schema Version Gate

Active Provider Foundation docs, examples, tests, and approval rows must use the
schema version defined in `docs/SCHEMA_VERSION_POLICY.md`.

Deprecated schema versions may be mentioned only as historical notes in the
schema-version policy and in validation code that rejects deprecated active
references.

### Project Status Gate

`PROJECT_STATUS.md` must reflect completed milestones and must not point to
stale next tasks after a governance cleanup has completed.

### Task Spec Gate

Every implementation task requires a real task spec file. A task id alone is not sufficient.

The task spec must define goal, allowed files, forbidden files, contract impact, ownership boundary, tests required, validation commands, rollback plan, and final report format.

### Contract Approval Gate

Implementation may use only contracts listed in `docs/CONTRACT_APPROVALS.md` with approval status `approved` and `implementation_allowed` set to `yes`.
