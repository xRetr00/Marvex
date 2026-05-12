# Provider Runtime Package

Status: minimal v1 provider creation boundary.

Ownership: Provider creation wiring for approved provider adapters.

Responsibility: Create an approved provider adapter from explicit runtime config.

Production bridge decision:

- Task 110 decides that ProviderRuntime must not own the production
  AssistantRuntime/Core bridge.
- A future separate runtime composition/factory layer may call ProviderRuntime
  to create an approved send-capable provider and inject that provider into the
  Core assistant-provider-stage helper.
- ProviderRuntime remains provider construction/provider-facing behavior only.
- Task 111 adds the first separate bridge proof. That proof calls
  `create_provider(ProviderRuntimeConfig(provider_name="fake"))` and then passes
  the resulting provider to Core. ProviderRuntime still does not import Core or
  AssistantRuntime.
- Task 112 makes CLI call RuntimeComposition instead of importing
  ProviderRuntime directly. ProviderRuntime remains the provider construction
  boundary behind RuntimeComposition.
- Task 113 adds a RuntimeComposition proof that requests the existing
  `lmstudio_responses` provider through `create_provider(...)`. ProviderRuntime
  still does not import RuntimeComposition, Core, or AssistantRuntime.

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
- Must not depend on AssistantRuntime or own assistant-turn result conversion.
