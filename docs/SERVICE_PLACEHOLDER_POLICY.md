# Service Placeholder Policy

Every service placeholder folder must remain README-only until its matching contract is listed in `docs/CONTRACT_APPROVALS.md` and a service-owned entrypoint task exists. Contract approval is necessary but not sufficient for implementation.

This applies to:

- `services/tool_worker`
- `services/intent_worker`
- `services/voice_worker`
- `services/desktop_agent`
- `services/shell`

Any non-README file in a service placeholder fails validation.

Approved service-owned entrypoint exceptions:

- `services/core`
- `services/provider_worker`

`services/core` may contain only `README.md`, `__init__.py`, and `main.py` for
the approved minimal local CoreService entrypoint. `services/provider_worker`
may contain only `README.md`, `__init__.py`, `models.py`, `controller.py`, and
`main.py` for the approved local ProviderWorker JSONL process boundary.
Arbitrary runtime/business logic, nested modules, adapter imports outside
approved boundaries, remote binding, and hidden autostart remain forbidden under
service entrypoint folders.

Service placeholder README files may describe intended ownership, scope limits, and contract requirements. They may not contain implementation code.

Service placeholders are not a substitute for runtime architecture boundaries. Runtime concerns such as factory, registry, dispatch, lifecycle, IPC, health, and versioning belong in runtime modules, not in placeholder service folders or port contracts. Approved service contracts still need lifecycle, IPC, health, version, docs, tests, and gates before implementation may land.

## Contract Mapping

| folder | required contract | status |
| --- | --- | --- |
| `services/core` | `CoreService` | approved minimal local entrypoint only |
| `services/provider_worker` | `ProviderWorker` | approved local ProviderWorker entrypoint only |
| `services/tool_worker` | `ToolWorker` | placeholder |
| `services/intent_worker` | `IntentWorker` | placeholder |
| `services/voice_worker` | `VoiceWorker` | placeholder |
| `services/desktop_agent` | `DesktopAgent` | placeholder |
| `services/shell` | `Shell` | placeholder |
