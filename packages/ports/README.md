# Ports Package

Status: skeleton only.

Ownership: Interface boundary between Core and external capabilities.

Responsibility: Future signature-only interfaces approved by contract tasks.

Forbidden responsibilities:

- Concrete adapter behavior.
- Core orchestration.
- Provider payload construction.
- HTTP calls.
- Policy decisions.

Dependency direction:

- May depend on approved contracts only.
- Must not depend on Core, adapters, CLI, telemetry implementation, services, or provider SDKs.
