# Core Package

Status: minimal Provider Foundation implementation.

Ownership: Core runtime boundary.

Responsibility: Turn lifecycle orchestration through approved contracts and
ports. Current behavior is limited to constructing provider requests, invoking
an injected `ProviderPort`, emitting telemetry lifecycle events, and returning
contract-compatible turn output.

Forbidden responsibilities:

- Provider-specific logic.
- Provider payload construction outside approved provider contracts.
- HTTP calls to providers.
- Tool execution.
- Memory, intent, voice, UI, desktop context, or proactive behavior.
- Hidden global state.

Dependency direction:

- May depend on approved contracts, ports, and telemetry sink contracts.
- Must not depend on adapters, CLI, services, or future workers.
