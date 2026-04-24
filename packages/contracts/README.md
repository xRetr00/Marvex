# Contracts Package

Status: skeleton only.

Ownership: Stable contract boundary.

Responsibility: Future implementation-neutral contract definitions after approval in `docs/CONTRACT_APPROVALS.md`.

Forbidden responsibilities:

- Business logic.
- Provider-specific logic.
- Core orchestration.
- Runtime side effects.

Dependency direction:

- Must remain dependency-light and implementation-neutral.
- May be used by Core, ports, adapters, CLI, and telemetry after contract approval.
- Must not depend on Core, ports, adapters, CLI, telemetry implementation, or services.
