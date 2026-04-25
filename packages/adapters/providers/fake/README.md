# Fake Provider Adapter

Status: test adapter only.

Ownership: deterministic provider adapter behavior for tests.

Responsibility: return contract-compatible `ProviderResponse` objects from `ProviderRequest` inputs.

Forbidden responsibilities:

- Real provider integration.
- Transport calls.
- Core runtime coordination.
- CLI behavior.
- Future module domains outside provider-adapter testing.
- Hidden mutable global state.

Dependency direction:

- May depend on approved contracts.
- Must not depend on Core, CLI, telemetry runtime, services, or LM Studio code.
