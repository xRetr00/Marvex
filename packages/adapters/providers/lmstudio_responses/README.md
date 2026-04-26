# LM Studio Responses Adapter Package

Status: native v1 provider adapter.

Ownership: LM Studio Responses-compatible provider adapter.

Responsibility: Convert approved provider contracts to LM Studio OpenAI-compatible Responses calls and convert SDK responses back to approved provider contracts.

Forbidden responsibilities:

- Fake provider behavior.
- Core orchestration.
- ProviderRuntime registration or selection.
- Model routing or fallback policy.
- Retry policy.
- Session storage or manual history reconstruction.
- Streaming, tools, MCP, memory, intent, voice, UI, desktop context, or proactive behavior.

Dependency direction:

- May depend on approved contracts and the OpenAI Python SDK.
- Must satisfy the provider port structurally.
- Must not be imported by Core, ports, CLI, or telemetry.
