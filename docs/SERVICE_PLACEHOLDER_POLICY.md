# Service Placeholder Policy

Every service placeholder folder must remain README-only until its matching contract is approved in `docs/CONTRACT_APPROVALS.md` and `implementation_allowed` is `yes`.

This applies to:

- `services/core`
- `services/provider_worker`
- `services/tool_worker`
- `services/intent_worker`
- `services/voice_worker`
- `services/desktop_agent`
- `services/shell`

Any non-README file in a service placeholder fails validation.

Service placeholder README files may describe intended ownership, forbidden work, and contract requirements. They may not contain implementation code.

Service placeholders are not a substitute for runtime architecture boundaries. Runtime concerns such as factory, registry, dispatch, and lifecycle belong in runtime modules, not in placeholder service folders or port contracts.

## Contract Mapping

| folder | required contract |
| --- | --- |
| `services/core` | `CoreService` |
| `services/provider_worker` | `ProviderWorker` |
| `services/tool_worker` | `ToolWorker` |
| `services/intent_worker` | `IntentWorker` |
| `services/voice_worker` | `VoiceWorker` |
| `services/desktop_agent` | `DesktopAgent` |
| `services/shell` | `Shell` |
