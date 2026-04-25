# LiteLLM Provider Adapter

Status: first real provider adapter.

Ownership: LiteLLM-backed provider adapter boundary.

Responsibility: Convert approved provider contracts to LiteLLM chat completion calls and convert LiteLLM responses back to approved provider contracts.

Forbidden responsibilities:

- Core orchestration.
- Provider routing policy.
- Conversation storage or hidden continuity.
- Direct provider HTTP clients.
- LM Studio native Responses behavior.
- UI, voice, desktop context, and future feature domains.

Dependency direction:

- May depend on approved contracts and the LiteLLM SDK.
- Must satisfy the provider port structurally.
- Must not be imported by Core, ports, CLI, telemetry, or service placeholders.
