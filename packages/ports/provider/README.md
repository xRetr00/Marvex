# Provider Port Package

Status: minimal Provider Foundation implementation.

Ownership: Provider interface boundary.

Responsibility: Define the provider-facing signature used by Core and provider
adapters.

Forbidden responsibilities:

- Concrete provider behavior.
- LM Studio payload construction.
- HTTP calls.
- Retry, routing, model policy, or fallback decisions.
- Core orchestration.

Dependency direction:

- May depend on approved contracts only.
- Must not depend on Core, adapters, CLI, telemetry implementation, or provider
  SDKs.
