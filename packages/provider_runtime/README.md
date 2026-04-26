# Provider Runtime Package

Status: minimal v1 provider creation boundary.

Ownership: Provider creation wiring for approved provider adapters.

Responsibility: Create an approved provider adapter from explicit runtime config.

Approved provider names:

- `fake`
- `litellm`
- `lmstudio_responses`

Forbidden responsibilities:

- Core orchestration.
- Provider behavior.
- Provider payload construction.
- New provider SDKs.
- Dynamic provider loading.
- Retry, fallback, model selection, health selection, or provider policy.
- Session storage or history management.
- Tool execution, MCP, streaming, memory, intent, UI, voice, or desktop context.

Dependency direction:

- May depend on provider ports and approved provider adapters.
- Must not depend on Core, CLI, telemetry implementation, services, or future workers.
