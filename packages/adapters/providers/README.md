# Provider Adapters Package

Status: Provider Foundation adapters implemented.

Ownership: Provider adapter placement boundary.

Responsibility: Concrete provider adapters that convert approved provider
contracts to provider SDK calls or deterministic fake responses.

Current approved adapters:

- `fake`
- `litellm`
- `lmstudio_responses`

Forbidden responsibilities:

- Core orchestration.
- Business policy.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Provider selection or runtime registration policy.

Dependency direction:

- May depend on approved contracts and approved provider SDKs.
- Must not be imported by Core, ports, CLI, or telemetry.
