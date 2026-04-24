# Contracts Package

Status: contracts-only implementation.

Ownership: Stable contract boundary.

Responsibility: Implementation-neutral Pydantic models and JSON schemas for approved v1 contracts.

Forbidden responsibilities:

- Business logic.
- Provider-specific logic.
- Core runtime coordination.
- Runtime side effects.
- HTTP calls.
- CLI behavior.
- Telemetry runtime behavior.

Dependency direction:

- Must remain dependency-light and implementation-neutral.
- May be used by Core, ports, adapters, CLI, and telemetry after contract approval.
- Must not depend on Core, ports, adapters, CLI, telemetry implementation, or services.
